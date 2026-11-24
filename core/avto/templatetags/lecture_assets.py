from django import template
from avto.lectures import asset_url
register = template.Library()
register.filter('lecture_url', asset_url)
