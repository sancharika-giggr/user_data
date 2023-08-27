import ast

from django.db import models


# Create your models here.


class Profile(models.Model):
    name = models.CharField(max_length=100)
    u_id = models.CharField(max_length=16, unique=True, null=True)
    email = models.EmailField()
    link = models.URLField()
    details = models.TextField(default=[])

    def get_details_list(self):
        details_list = ast.literal_eval(str(self.details))
        return details_list

    def set_details_list(self, details_list):
        self.details = ','.join(details_list)

    def __str__(self):
        return self.name


class UserAgentLog(models.Model):
    name = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(default=[])

    def get_details_list(self):
        details_list = ast.literal_eval(str(self.details))
        return details_list

    def set_details_list(self, details_list):
        self.details = ','.join(details_list)

    def __str__(self):
        return self.name
