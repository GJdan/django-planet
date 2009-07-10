# -*- coding: utf-8 -*-

import os
from datetime import datetime

from django.http import HttpResponse
from django.utils import feedgenerator
from django.utils.cache import patch_vary_headers
from django.core.urlresolvers import reverse
from django.conf import settings
from django.shortcuts import get_object_or_404, Http404
from django.template.defaultfilters import linebreaks, escape, capfirst
from django.utils.translation import ugettext_lazy as _

from atompub import atomformat
from planet.models import Post, Site, Subscriber, Feed
from tagging.models import Tag


ITEMS_PER_FEED = getattr(settings, 'PLANET_ITEMS_PER_FEED', 50)

class BasePostFeed(atomformat.Feed):
    def __init__(self, *args, **kwargs):
        super(BasePostFeed, self).__init__(args, kwargs)
        self.site = Site.objects.get(pk=settings.SITE_ID)
        
    def item_id(self, post):
        return post.guid
    
    def item_title(self, post):
        return post.title
    
    def item_updated(self, post):
        return post.date_modified
    
    def item_published(self, post):
        return post.date_created
    
    def item_content(self, post):
        return {"type" : "html", }, linebreaks(escape(post.content))
    
    def item_links(self, post):
        return [{"href" : reverse("post_show", args=( post.pk,))}]
    
    def item_authors(self, post):
        return [{"name" : post.author}]

class PostFeed(BasePostFeed):
    def feed_id(self):
        return reverse("posts_list")
    
    def feed_title(self):
        return _("Posts in %s") % self.site.name

    def feed_subtitle(self):
        return _("All posts")

    def feed_updated(self):
        qs = Post.objects.filter(feed__subscriber__site=self.site)
        # We return an arbitrary date if there are no results, because there
        # must be a feed_updated field as per the Atom specifications, however
        # there is no real data to go by, and an arbitrary date can be static.
        if qs.count() == 0:
            return datetime(year=2008, month=7, day=1)
        return qs.latest('date_created').date_created

    def feed_links(self):
        return ({'href': reverse('posts_list')},)

    def items(self):
        posts_list = Post.objects.filter(feed__subscriber__site=self.site
            ).order_by("-date_created")[:ITEMS_PER_FEED]
        return posts_list

class SubscriberFeed(BasePostFeed):
    def get_object(self, params):
        return get_object_or_404(Subscriber, pk=params[0], is_active=True)
    
    def feed_id(self, subscriber):
        return reverse("subscriber_show", args=(subscriber.pk, ))
    
    def feed_title(self, subscriber):
        return _("Posts by %s - %s") % (subscriber.name, self.site.name)

    def feed_updated(self, subscriber):
        qs = Post.objects.filter(feed__subscriber=subscriber).distinct()
        # We return an arbitrary date if there are no results, because there
        # must be a feed_updated field as per the Atom specifications, however
        # there is no real data to go by, and an arbitrary date can be static.
        if qs.count() == 0:
            return datetime(year=2008, month=7, day=1)
        return qs.latest('date_created').date_created

    def feed_links(self, subscriber):
        return ({'href': reverse("subscriber_show", args=(subscriber.pk, ))},)

    def items(self, subscriber):
        return Post.objects.filter(feed__subscriber=subscriber,
            ).distinct().order_by("-date_created")[:ITEMS_PER_FEED]

class BlogFeed(BasePostFeed):
    def get_object(self, params):
        return get_object_or_404(Feed, pk=params[0], is_active=True)
    
    def feed_id(self, feed):
        return reverse("feed_show", args=(feed.pk, ))
    
    def feed_title(self, feed):
        return _("Posts in %s - %s") % (feed.title, self.site.name)

    def feed_subtitle(self, feed):
        return "%s - %s" % (feed.tagline, feed.link)

    def feed_updated(self, feed):
        qs = Post.objects.filter(feed=feed,
            feed__subscriber__site=self.site).distinct()
        # We return an arbitrary date if there are no results, because there
        # must be a feed_updated field as per the Atom specifications, however
        # there is no real data to go by, and an arbitrary date can be static.
        if qs.count() == 0:
            return datetime(year=2008, month=7, day=1)
        return qs.latest('date_created').date_created

    def feed_links(self, feed):
        return ({'href': reverse("feed_show", args=(feed.pk, ))},)

    def items(self, feed):
        return Post.objects.filter(feed=feed,
            feed__subscriber__site=self.site).distinct(
            ).order_by("-date_created")[:ITEMS_PER_FEED]

class TagFeed(BasePostFeed):
    def get_object(self, params):
        return get_object_or_404(Tag, name=params[0])
    
    def feed_id(self, tag):
        return reverse("tag_show", args=(tag.pk, ))
    
    def feed_title(self, tag):
        return _("Posts under %s tag - %s") % (tag, self.site.name)

    def feed_updated(self, tag):
        qs = Post.objects.filter(tags__name=tag,
            feed__subscriber__site=self.site).distinct()
        # We return an arbitrary date if there are no results, because there
        # must be a feed_updated field as per the Atom specifications, however
        # there is no real data to go by, and an arbitrary date can be static.
        if qs.count() == 0:
            return datetime(year=2008, month=7, day=1)
        return qs.latest('date_created').date_created

    def feed_links(self, tag):
        return ({'href': reverse("tag_show", args=(tag.pk, ))},)

    def items(self, tag):
        return Post.objects.filter(tags__name=tag, feed__subscriber__site=self.site
            ).distinct().order_by("-date_created")[:ITEMS_PER_FEED]

class SubscriberTagFeed(BasePostFeed):
    def __init__(self, *args, **kwargs):
        super(SubscriberTagFeed, self).__init__(args, kwargs)
        self.tag = kwargs["tag"]
    
    def get_object(self, params):
        return get_object_or_404(Subscriber, pk=params[0], is_active=True)
    
    def feed_id(self, subscriber):
        return reverse("by_tag_subscriber_show", args=(subscriber.pk, self.tag))
    
    def feed_title(self, subscriber):
        return _("Posts by %s under %s tag - %s")\
            % (subscriber.name, self.tag, self.site.name)

    def feed_updated(self, subscriber):
        qs = Post.objects.filter(feed__subscriber=subscriber,
            tags__name=self.tag).distinct()
        # We return an arbitrary date if there are no results, because there
        # must be a feed_updated field as per the Atom specifications, however
        # there is no real data to go by, and an arbitrary date can be static.
        if qs.count() == 0:
            return datetime(year=2008, month=7, day=1)
        return qs.latest('date_created').date_created

    def feed_links(self, subscriber):
        return ({'href': reverse("by_tag_subscriber_show", args=(subscriber.pk, self.tag))},)

    def items(self, subscriber):
        return Post.objects.filter(
            feed__subscriber=subscriber, tags__name=self.tag
            ).distinct().order_by("-date_created")[:ITEMS_PER_FEED]

class SubscriberFeedChooser:
    def __init__(self, *args, **kwargs):
        self.request = args[1]
        self.url = args[0]

    def get_feed(self, params):
        check_params = params.split("/")
        if len(check_params) == 1:
            return SubscriberFeed(self.url, self.request).get_feed(params)
        else:
            if not len(check_params) == 3:
                raise Http404, "Feed does not exist"

            if not check_params[1] == "tags":
                raise Http404, "Feed does not exist"
            
            tag = check_params[2]
            return SubscriberTagFeed(self.url, self.request, tag=tag).get_feed(params)

def rss_feed(request, tag=None, subscriber_id=None):
    site = get_object_or_404(Site, pk=settings.SITE_ID)

    params_dict = {"feed__subscriber__site": site}

    pretitle = ""
    title = "%s (RSS Feed)" % site.title
    
    if tag:
        params_dict.update({"tags__name": tag})
        pretitle = "%s %s " % (tag, _("in"))

    if subscriber_id:
        params_dict.update({"feed__subscriber": subscriber_id})
        subscriber = Subscriber.objects.get(pk=subscriber_id)
        pretitle = "%s %s " % (subscriber.name, _("in"))

    try:
        posts_count = settings.FJ_EXTENSION_ITEMS_PER_FEED
    except AttributeError:
        posts_count = 50

    object_list = Post.objects.filter(**params_dict).distinct()[:posts_count]
    
    feed = feedgenerator.Rss201rev2Feed(title=pretitle + title,
        link=site.url, description=site.description,
        feed_url=os.path.join(site.url, reverse("default_feed")))

    for post in object_list:
        feed.add_item(
            title = '%s: %s' % (post.feed.name, post.title),
            link = reverse("post_show", args=(post.pk,)),
            description = post.content,
            author_email = post.author_email,
            author_name = post.author,
            pubdate = post.date_modified,
            unique_id = post.link,
            categories = [tag.name for tag in post.tags.all()]
        )
    
    response = HttpResponse(mimetype=feed.mime_type)

    # per host caching
    patch_vary_headers(response, ['Host'])
    feed.write(response, 'utf-8')
    
    return response