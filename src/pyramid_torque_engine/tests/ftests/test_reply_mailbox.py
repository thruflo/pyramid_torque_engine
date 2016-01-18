# -*- coding: utf-8 -*-

"""Test the ``request.torque`` client api."""

import unittest
import transaction
import pyramid_basemodel as bm

from pyramid_torque_engine import repo
from pyramid_simpleauth import model as simpleauth_model

from . import boilerplate
from . import model

from mock import Mock


class TestReplyMailbox(boilerplate.AppTestCase):
    """Test the ``orm.ReplayMailbox`` class."""

    def test_get_or_create(self):
        """get_or_create from ReplayMailbox should work..."""

        context = model.factory()
        context_id = context.id
        with transaction.manager:
            user = boilerplate.createUser()
            user_id = user.id
        user = simpleauth_model.User.query.get(user_id)

        # Should create a new one and return it.
        with transaction.manager:
            mailbox = repo.get_or_create_reply_mailbox(user, context)
            bm.Session.flush()
            self.assertTrue(mailbox.digest)
            self.assertEqual(mailbox.target_oid, context_id)
            self.assertEqual(mailbox.user_id, user_id)

        # If we do it again, we should get the one already created.
        with transaction.manager:
            bm.Session.add(user)
            bm.Session.add(context)
            mailbox = repo.get_or_create_reply_mailbox(user, context)
            self.assertTrue(mailbox.digest)
            self.assertEqual(mailbox.target_oid, context_id)
            self.assertEqual(mailbox.user_id, user_id)
