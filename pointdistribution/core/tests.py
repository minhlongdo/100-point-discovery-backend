from django.test import TestCase
from django.db.utils import IntegrityError
from rest_framework.test import APIRequestFactory
from datetime import date


from .models import Member, PointDistribution, GivenPoint, GivenPointArchived
from .views import PointDistributionHistory, PointDistributionWeek, MemberList, SendPoints, \
    ValidateProvisionalPointDistribution

# TEST MODELS


class MemberModelTest(TestCase):
    def setUp(self):
        self.entry = Member(name="My entry title")

    def test_string_representation(self):
        self.assertEqual(str(self.entry), self.entry.email)

    def test_save(self):
        self.entry.save()


class PointDistributionTest(TestCase):
    def test_string_representation_provisional(self):
        entry = PointDistribution(week="1970-01-01", is_final=False)
        self.assertEqual(str(entry), str(entry.week) + ", provisional")
        entry = PointDistribution(week="1970-01-01", is_final=True)
        self.assertEqual(str(entry), str(entry.week) + ", final")

    def test_save(self):
        entry = PointDistribution(week="1970-01-01", is_final=True)
        entry.save()


class GivenPointTest(TestCase):
    def setUp(self):
        self.entry1 = Member(name="Name1", email="name1@email.com")
        self.entry2 = Member(name="Name2", email="name2@email.com")
        self.entry1.save()
        self.entry2.save()
        self.entry_point_distribution = PointDistribution(week="1970-01-01", is_final=True)
        self.entry_point_distribution.save()

    def test_string_representation(self):
        entry = GivenPoint(from_member=self.entry1, to_member=self.entry2, points=30, week="1970-01-01")
        self.assertEqual(str(entry), str(entry.week) + ", from " + str(entry.from_member) + " to " + str(entry.to_member))

    def test_save(self):
        entry = GivenPoint(from_member=self.entry1, to_member=self.entry2,
                           point_distribution=self.entry_point_distribution, points=30, week="1970-01-01")
        entry.save()

    def test_unique_together_fields(self):
        entry1 = GivenPoint(from_member=self.entry1, to_member=self.entry2,
                            point_distribution=self.entry_point_distribution, points=30, week="1970-01-01")
        entry2 = GivenPoint(from_member=self.entry1, to_member=self.entry2,
                            point_distribution=self.entry_point_distribution, points=50, week="1970-01-01")
        entry1.save()
        self.assertRaises(IntegrityError, entry2.save)

# TEST VIEWS


class MemberListTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_full_history(self):
        self.entry1 = Member(name="Name1", email="name1@email.com")
        self.entry2 = Member(name="Name2", email="name2@email.com")
        self.entry1.save()
        self.entry2.save()
        request = self.factory.get('/v1/members/')
        response = MemberList.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [{"name": "Name1", "email": "name1@email.com"},
                                         {"name": "Name2", "email": "name2@email.com"}])

    def test_create_member(self):
        request = self.factory.post('/v1/members/', {"name": "Name", "email": "name@email.com"})
        response = MemberList.as_view()(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, {"name": "Name", "email": "name@email.com"})


class PointDistributionHistoryTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_empty_history(self):
        request = self.factory.get('/v1/points/distribution/history/')
        response = PointDistributionHistory.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])


class SendPointsTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.entry1 = Member(name="Name1", email="name1@email.com")
        self.entry2 = Member(name="Name2", email="name2@email.com")
        self.entry1.save()
        self.entry2.save()
        self.today = date.today().isoformat()

    def test_post(self):
        distr = {
            'given_points': [
                {
                    'from_member': 'name1@email.com',
                    'to_member': 'name1@email.com',
                    'points': 0,
                    'week': self.today
                },
                {
                    'from_member': 'name1@email.com',
                    'to_member': 'name2@email.com',
                    'points': 100,
                    'week': self.today
                }
            ],
            'week': self.today
        }
        request = self.factory.post('/v1/points/distribution/send/', distr, format='json')
        response = SendPoints.as_view()(request)
        self.assertEqual(response.status_code, 200)
        distr['is_final'] = False
        self.assertEqual(response.data, distr)

    def test_put(self):
        distr = {
            'given_points': [
                {
                    'from_member': 'name1@email.com',
                    'to_member': 'name1@email.com',
                    'points': 0,
                    'week': self.today
                },
                {
                    'from_member': 'name1@email.com',
                    'to_member': 'name2@email.com',
                    'points': 100,
                    'week': self.today
                }
            ],
            'week': self.today
        }
        request = self.factory.post('/v1/points/distribution/send/', distr, format='json')
        response = SendPoints.as_view()(request)
        self.assertEqual(response.status_code, 200)
        distr2 = {
            'given_points': [
                {
                    'from_member': 'name1@email.com',
                    'to_member': 'name1@email.com',
                    'points': 50,
                    'week': self.today
                }
            ],
            'week': self.today
        }
        request = self.factory.put('/v1/points/distribution/send/', distr2, format='json')
        response = SendPoints.as_view()(request)
        self.assertEqual(response.status_code, 200)
        distr['given_points'][0]['points'] = 50
        distr['is_final'] = False
        self.assertEqual(response.data, distr)

    def test_post_not_all_members_should_return_400(self):
        distr = {
            'given_points': [
                {
                    'from_member': 'name1@email.com',
                    'to_member': 'name1@email.com',
                    'points': 0,
                    'week': self.today
                }
            ],
            'week': self.today
        }
        request = self.factory.post('/v1/points/distribution/send/', distr, format='json')
        response = SendPoints.as_view()(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'detail': "Some members haven't been graded yet"})


class PointDistributionWeekTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.entry1 = Member(name="Name1", email="name1@email.com")
        self.entry1.save()
        self.today = date.today().isoformat()

    def test_point_distribution(self):
        distr = {
            'given_points': [
                {
                    'from_member': 'name1@email.com',
                    'to_member': 'name1@email.com',
                    'points': 0,
                    'week': self.today
                }
            ],
            'week': self.today
        }
        request = self.factory.post('/v1/points/distribution/send/', distr, format='json')
        response = SendPoints.as_view()(request)
        self.assertEqual(response.status_code, 200)
        request = self.factory.get('/v1/points/distribution/%s/' % self.today)
        response = PointDistributionWeek.as_view()(request, week=self.today)
        self.assertEqual(response.status_code, 200)
        distr['is_final'] = False
        self.assertEqual(response.data, distr)

    def test_point_distribution_non_existant(self):
        request = self.factory.get('/v1/points/distribution/%s/' % self.today)
        response = PointDistributionWeek.as_view()(request, week=self.today)
        self.assertEqual(response.status_code, 404)


class ValidateProvisionalPointDistributionTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.entry1 = Member(name="Name1", email="name1@email.com")
        self.entry2 = Member(name="Name2", email="name2@email.com")
        self.entry1.save()
        self.entry2.save()
        self.today = date.today().isoformat()

    def test_valid_point_distribution(self):
        distr1 = {
            'given_points': [
                {
                    'from_member': 'name1@email.com',
                    'to_member': 'name1@email.com',
                    'points': 51,
                    'week': self.today
                },
                {
                    'from_member': 'name1@email.com',
                    'to_member': 'name2@email.com',
                    'points': 49,
                    'week': self.today
                }
            ],
            'week': self.today
        }
        request = self.factory.post('/v1/points/distribution/send/', distr1, format='json')
        response = SendPoints.as_view()(request)
        self.assertEqual(response.status_code, 200)
        distr2 = {
            'given_points': [
                {
                    'from_member': 'name2@email.com',
                    'to_member': 'name1@email.com',
                    'points': 51,
                    'week': self.today
                },
                {
                    'from_member': 'name2@email.com',
                    'to_member': 'name2@email.com',
                    'points': 49,
                    'week': self.today
                }
            ],
            'week': self.today
        }
        request = self.factory.post('/v1/points/distribution/send/', distr2, format='json')
        response = SendPoints.as_view()(request)
        self.assertEqual(response.status_code, 200)
        request = self.factory.put('/v1/points/distribution/send/', {'week': self.today})
        response = ValidateProvisionalPointDistribution.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['is_final'], True)
        self.assertEqual(len(response.data['given_points']), 2)
        self.assertEqual(response.data['given_points'][0]['from_member'], None)
        self.assertEqual(response.data['given_points'][1]['from_member'], None)
        self.assertEqual(len(GivenPointArchived.objects.all()), 4)

    def test_points_between_members_dont_match(self):
        distr1 = {
            'given_points': [
                {
                    'from_member': 'name1@email.com',
                    'to_member': 'name1@email.com',
                    'points': 51,
                    'week': self.today
                },
                {
                    'from_member': 'name1@email.com',
                    'to_member': 'name2@email.com',
                    'points': 49,
                    'week': self.today
                }
            ],
            'week': self.today
        }
        request = self.factory.post('/v1/points/distribution/send/', distr1, format='json')
        response = SendPoints.as_view()(request)
        self.assertEqual(response.status_code, 200)
        distr2 = {
            'given_points': [
                {
                    'from_member': 'name2@email.com',
                    'to_member': 'name1@email.com',
                    'points': 0,
                    'week': self.today
                },
                {
                    'from_member': 'name2@email.com',
                    'to_member': 'name2@email.com',
                    'points': 49,
                    'week': self.today
                }
            ],
            'week': self.today
        }
        request = self.factory.post('/v1/points/distribution/send/', distr2, format='json')
        response = SendPoints.as_view()(request)
        self.assertEqual(response.status_code, 200)
        request = self.factory.put('/v1/points/distribution/send/', {'week': self.today})
        response = ValidateProvisionalPointDistribution.as_view()(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data,
                         {'detail': 'There is a conflict of points with at lest one member in the group'})

    def test_points_dont_add_up_to_100(self):
        distr1 = {
            'given_points': [
                {
                    'from_member': 'name1@email.com',
                    'to_member': 'name1@email.com',
                    'points': 51,
                    'week': self.today
                },
                {
                    'from_member': 'name1@email.com',
                    'to_member': 'name2@email.com',
                    'points': 10,
                    'week': self.today
                }
            ],
            'week': self.today
        }
        request = self.factory.post('/v1/points/distribution/send/', distr1, format='json')
        response = SendPoints.as_view()(request)
        self.assertEqual(response.status_code, 200)
        distr2 = {
            'given_points': [
                {
                    'from_member': 'name2@email.com',
                    'to_member': 'name1@email.com',
                    'points': 51,
                    'week': self.today
                },
                {
                    'from_member': 'name2@email.com',
                    'to_member': 'name2@email.com',
                    'points': 10,
                    'week': self.today
                }
            ],
            'week': self.today
        }
        request = self.factory.post('/v1/points/distribution/send/', distr2, format='json')
        response = SendPoints.as_view()(request)
        self.assertEqual(response.status_code, 200)
        request = self.factory.put('/v1/points/distribution/send/', {'week': self.today})
        response = ValidateProvisionalPointDistribution.as_view()(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'detail': 'Sum of points different than 100'})

    def test_repeated_points(self):
        distr1 = {
            'given_points': [
                {
                    'from_member': 'name1@email.com',
                    'to_member': 'name1@email.com',
                    'points': 50,
                    'week': self.today
                },
                {
                    'from_member': 'name1@email.com',
                    'to_member': 'name2@email.com',
                    'points': 50,
                    'week': self.today
                }
            ],
            'week': self.today
        }
        request = self.factory.post('/v1/points/distribution/send/', distr1, format='json')
        response = SendPoints.as_view()(request)
        self.assertEqual(response.status_code, 200)
        distr2 = {
            'given_points': [
                {
                    'from_member': 'name2@email.com',
                    'to_member': 'name1@email.com',
                    'points': 50,
                    'week': self.today
                },
                {
                    'from_member': 'name2@email.com',
                    'to_member': 'name2@email.com',
                    'points': 50,
                    'week': self.today
                }
            ],
            'week': self.today
        }
        request = self.factory.post('/v1/points/distribution/send/', distr2, format='json')
        response = SendPoints.as_view()(request)
        self.assertEqual(response.status_code, 200)
        request = self.factory.put('/v1/points/distribution/send/', {'week': self.today})
        response = ValidateProvisionalPointDistribution.as_view()(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'detail': 'Several team members have the same amount of points'})

    def test_not_all_members_gave_points(self):
        distr1 = {
            'given_points': [
                {
                    'from_member': 'name1@email.com',
                    'to_member': 'name1@email.com',
                    'points': 51,
                    'week': self.today
                },
                {
                    'from_member': 'name1@email.com',
                    'to_member': 'name2@email.com',
                    'points': 49,
                    'week': self.today
                }
            ],
            'week': self.today
        }
        request = self.factory.post('/v1/points/distribution/send/', distr1, format='json')
        response = SendPoints.as_view()(request)
        self.assertEqual(response.status_code, 200)
        request = self.factory.put('/v1/points/distribution/send/', {'week': self.today})
        response = ValidateProvisionalPointDistribution.as_view()(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'detail': "Not all members gave points to their colleagues"})
