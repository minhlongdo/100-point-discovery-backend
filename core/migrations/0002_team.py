# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-03-17 16:43
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Team',
            fields=[
                ('instance_id', models.CharField(max_length=255, primary_key=True, serialize=False)),
                ('instance_name', models.CharField(max_length=255)),
            ],
        ),
    ]
