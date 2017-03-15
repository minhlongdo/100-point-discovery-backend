from .models import Member, GivenPoint, GivenPointArchived, PointDistribution
from .serializers import MemberSerializer, GivenPointArchivedSerializer, PointDistributionSerializer, \
    GivenPointSerializer
from .points_operation import validate_provisional_point_distribution, check_batch_includes_all_members, \
    check_all_point_values_are_valid
from .utils import is_current_week, get_member, filter_final_points_distributions, get_all_members, \
    get_given_point_models, get_monday_from_date, DATE_PATTERN, concatenate_and_hash
from .exceptions import NotCurrentWeekException

from django.http import Http404

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response

from pointdistribution.pointdistribution.settings import VSTS_BASE_URL, SETTING_MANAGE_BASE_URL
from pointdistribution.core.utils import concatenate_and_hash

import hashlib
import requests
import logging


def construct_url_for_project(instance_name):
    request_url = VSTS_BASE_URL.format(instance_name)
    return request_url


class MemberList(APIView):
    """
    Get all the members, create a member

    Endpoint: **/v1/members/?instance_id=1234**  **/v1/members**

    Methods: *GET POST*
    """
    def get(self, request):
        instance_id = request.GET.get('instance_id', '')
        vsts_instance = request.GET.get('instance_name', '')
        user_email = request.GET.get('user_email', '')

        vsts_token_request = requests.get(SETTING_MANAGE_BASE_URL, params={'instance_id': instance_id,
                                                                           'user_email': user_email})
        vsts_token = vsts_token_request.json()['vsts_token']
        email_account_name = user_email.split('@')

        vsts_request_url = construct_url_for_project(vsts_instance)

        r = requests.get(vsts_request_url, auth=(email_account_name, vsts_token))

        projects = r.json()['value']

        for project in projects:
            # Get all team members
            project_id = project['id']
            r = requests.get('https://{}.visualstudio.com/DefaultCollection/_apis/projects/{}/teams'.format(vsts_instance,
                                                                                                      project_id),
                             auth=(email_account_name, vsts_token))
            team_id = r.json()['id']

            team_member_data = requests.get('https://{}.visualstudio.com/DefaultCollection/_apis/projects/{}/teams/{}/'
                                            'members?api_version=1.0'.format(vsts_instance, project_id, team_id),
                                            auth=(email_account_name, vsts_token))
            team_members = team_member_data.json()['value']

            for team_member in team_members:
                email = team_member['uniqueName']
                name = team_member['displayName']
                identifier = concatenate_and_hash(email, instance_id)

                try:
                    member = Member.objects.filter(identifier=identifier, email=email)
                    if len(member) == 1:
                        continue

                except Member.DoesNotExist:
                    logging.info("Could not find member, creating new member with the following information;"
                                 "name={}, email{}, instance_id={}, identifier={}".format(name, email,
                                                                                          instance_id, identifier))
                    Member.objects.create(email=email, name=name, instance_id=instance_id, identifier=identifier)

                except Exception as e:
                    logging.error("Something unexpected happened during the member filter", e)

        # Now fetch all the members and return them
        members = Member.objects.filter(instance_id=instance_id)
        serializer = MemberSerializer(members, many=True)
        return Response(serializer.data)

    def post(self, request):
        email = request.data['email']
        instance_id = request.data['instance_id']
        request.data['identifier'] = concatenate_and_hash(email, instance_id)
        serializer = MemberSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)


class MemberPointsHistory(APIView):
    """
    Get all the given points a user received

    Endpoint: **/v1/member/history/<email>/?instance_id=1234**

    Methods: *GET*
    """
    @staticmethod
    def get_given_points_member(member, instance_id):
        try:
            return GivenPointArchived.objects.filter(to_member=member, instance_id=instance_id)
        except GivenPointArchived.DoesNotExist:
            raise Http404

    def get(self, request, email):
        instance_id = request.GET.get('instance_id', '')
        member = get_member(email, instance_id)
        given_points = self.get_given_points_member(member, instance_id)
        serializer = GivenPointArchivedSerializer(given_points, many=True)
        return Response(serializer.data)


class PointDistributionHistory(APIView):
    """
    Get all the past point distributions

    Endpoint: **/v1/points/distribution/history/?instance_id=1234**

    Methods: *GET*
    """
    def get(self, request):
        instance_id = request.GET.get('instance_id', '')
        point_distribution_history = filter_final_points_distributions(instance_id)
        serializer = PointDistributionSerializer(point_distribution_history, many=True)
        return Response(serializer.data)


class SendPoints(APIView):
    """
    Send points to team members. Date must be the current week

    Endpoint: **/v1/point/distribution/send**

    Methods: *POST PUT*

    Body:

    ```
    {
        "given_points": [
          {
            "to_member": "member1@email.com",
            "points": 30,
            "from_member": "me@me.com",
            "instance_id": "1234"
          },
          {
            "to_member": "member2@email.com",
            "points": 0,
            "from_member": "me@me.com",
            "instance_id": "1234"
          }
        ],
        "date": "2017-01-21",
        "instance_id": "1234"
    }
    ```
    """
    @staticmethod
    def get_or_create_point_distribution(date, week, instance_id, identifier):
        obj, _ = PointDistribution.objects.get_or_create(instance_id=instance_id, week=week, is_final=False,
                                                         identifier=identifier, defaults={'date': date})
        return obj

    def post(self, request):
        date = request.data['date']
        instance_id = request.data['instance_id']
        if not is_current_week(date, DATE_PATTERN):
            raise NotCurrentWeekException()
        week = get_monday_from_date(date, DATE_PATTERN)
        request.data['identifier'] = concatenate_and_hash(week, instance_id)
        point_distribution = self.get_or_create_point_distribution(date, week, instance_id, request.data['identifier'])
        members_set = set(get_all_members(instance_id).values_list('email', flat=True))
        given_points = request.data['given_points']
        check_batch_includes_all_members(given_points, members_set)
        check_all_point_values_are_valid(given_points)
        request.data['week'] = week
        for given_point in request.data['given_points']:
            given_point['week'] = week
            given_point['to_member'] = concatenate_and_hash(given_point['to_member'], instance_id)
            given_point['from_member'] = concatenate_and_hash(given_point['from_member'], instance_id)
        serializer = PointDistributionSerializer(point_distribution, data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        for given_point in serializer.data['given_points']:
            given_point['to_member'] = Member.objects.get(identifier=given_point['to_member']).email
            given_point['from_member'] = Member.objects.get(identifier=given_point['from_member']).email
        return Response(serializer.data)

    def put(self, request):
        date = request.data['date']
        instance_id = request.data['instance_id']
        if not is_current_week(date, DATE_PATTERN):
            raise NotCurrentWeekException()
        given_points = request.data['given_points']
        check_all_point_values_are_valid(given_points)
        week = get_monday_from_date(date, DATE_PATTERN)
        request.data['identifier'] = concatenate_and_hash(week, instance_id)
        given_points_models = get_given_point_models(given_points, week, instance_id)
        for idx, model in enumerate(given_points_models):
            given_points[idx]['from_member'] = concatenate_and_hash(given_points[idx]['from_member'], instance_id)
            given_points[idx]['to_member'] = concatenate_and_hash(given_points[idx]['to_member'], instance_id)
            given_points[idx]['week'] = week
            serializer = GivenPointSerializer(model, data=given_points[idx])
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            serializer.save()
        point_distribution = self.get_or_create_point_distribution(date, week, instance_id, request.data['identifier'])
        serializer = PointDistributionSerializer(point_distribution)
        for given_point in serializer.data['given_points']:
            given_point['to_member'] = Member.objects.get(identifier=given_point['to_member']).email
            given_point['from_member'] = Member.objects.get(identifier=given_point['from_member']).email
        return Response(serializer.data)


class PointDistributionWeek(APIView):
    """
    Get a point distribution of a past week

    Endpoint: **/v1/point/distribution/YYYY-MM-DD/?instance_id=1234**

    Methods: *GET*
    """
    @staticmethod
    def get_object(week, instance_id):
        try:
            return PointDistribution.objects.get(instance_id=instance_id, week=week)
        except PointDistribution.DoesNotExist:
            raise Http404

    def get(self, request, week):
        instance_id = request.GET.get('instance_id', '')
        point_distribution = self.get_object(week, instance_id)
        serializer = PointDistributionSerializer(point_distribution)
        return Response(serializer.data)


class ValidateProvisionalPointDistribution(APIView):
    """
    Validate a point distribution

    Endpoint: **/v1/point/distribution/validate**

    Methods: *PUT*

    Body:

    `{"week":"YYYY-MM-DD", "instance_id":"1234"}`
    """
    @staticmethod
    def get_point_distribution(week, instance_id):
        try:
            return PointDistribution.objects.get(week=week, instance_id=instance_id)
        except PointDistribution.DoesNotExist:
            raise Http404

    def put(self, request):
        week = request.data['week']
        instance_id = request.data['instance_id']
        point_distribution = self.get_point_distribution(week, instance_id)
        members_set = set(get_all_members(instance_id))
        validate_provisional_point_distribution(point_distribution, members_set)
        point_distribution.is_final = True
        point_distribution.save()
        serializer = PointDistributionSerializer(point_distribution)
        return Response(serializer.data)
