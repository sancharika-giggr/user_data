from django.db import models


# Create your models here.


class Profile(models.Model):
    name = models.CharField(max_length=100)
    u_id = models.CharField(max_length=16, unique=True, null=False, blank=False)
    link = models.URLField()


class UserAgentLog(models.Model):
    user_agent = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user_agent
