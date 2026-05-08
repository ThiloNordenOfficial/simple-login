import arrow

import cron
from app.db import Session
from app.mail_sender import mail_sender
from app.models import (
    Alias,
    AliasDeleteReason,
    AliasExpiryAction,
    CoinbaseSubscription,
    ApiToCookieToken,
    ApiKey,
    User,
)
from tests.utils import create_new_user


def test_notify_manual_sub_end(flask_client):
    user = create_new_user()
    CoinbaseSubscription.create(
        user_id=user.id, end_at=arrow.now().shift(days=13, hours=2), commit=True
    )
    cron.notify_manual_sub_end()


def test_cleanup_tokens(flask_client):
    user = create_new_user()
    api_key = ApiKey.create(
        user_id=user.id,
        commit=True,
    )
    id_to_clean = ApiToCookieToken.create(
        user_id=user.id,
        api_key_id=api_key.id,
        commit=True,
        created_at=arrow.now().shift(days=-1),
    ).id

    id_to_keep = ApiToCookieToken.create(
        user_id=user.id,
        api_key_id=api_key.id,
        commit=True,
    ).id
    cron.delete_expired_tokens()
    assert ApiToCookieToken.get(id_to_clean) is None
    assert ApiToCookieToken.get(id_to_keep) is not None


def test_cleanup_users():
    u_delete_none_id = create_new_user().id
    u_delete_grace_has_expired = create_new_user()
    u_delete_grace_has_expired_id = u_delete_grace_has_expired.id
    u_delete_grace_has_not_expired = create_new_user()
    u_delete_grace_has_not_expired_id = u_delete_grace_has_not_expired.id
    now = arrow.now()
    u_delete_grace_has_expired.delete_on = now.shift(days=-(cron.DELETE_GRACE_DAYS + 1))
    u_delete_grace_has_not_expired.delete_on = now.shift(
        days=-(cron.DELETE_GRACE_DAYS - 1)
    )
    Session.flush()
    cron.clear_users_scheduled_to_be_deleted()
    assert User.get(u_delete_none_id) is not None
    assert User.get(u_delete_grace_has_not_expired_id) is not None
    assert User.get(u_delete_grace_has_expired_id) is None


def test_process_expired_aliases_disables_alias(flask_client):
    user = create_new_user()
    alias = Alias.create_new_random(user)
    alias.expiry_date = arrow.now().shift(hours=-1)
    alias.expiry_action = AliasExpiryAction.Disable
    alias.expiry_notify_user = False
    Session.commit()

    cron.process_expired_aliases()

    assert alias.enabled is False
    assert alias.expiry_date is None


def test_process_expired_aliases_moves_to_trash(flask_client):
    user = create_new_user()
    alias = Alias.create_new_random(user)
    alias.expiry_date = arrow.now().shift(hours=-1)
    alias.expiry_action = AliasExpiryAction.DeleteToTrash
    alias.expiry_notify_user = False
    Session.commit()

    cron.process_expired_aliases()

    assert alias.delete_on is not None
    assert alias.delete_reason == AliasDeleteReason.ManualAction
    assert alias.expiry_date is None


def test_process_expired_aliases_skips_future_expiry(flask_client):
    user = create_new_user()
    alias = Alias.create_new_random(user)
    alias.expiry_date = arrow.now().shift(days=1)
    alias.expiry_action = AliasExpiryAction.Disable
    Session.commit()

    cron.process_expired_aliases()

    assert alias.enabled is True
    assert alias.expiry_date is not None


def test_process_expired_aliases_skips_already_disabled(flask_client):
    user = create_new_user()
    alias = Alias.create_new_random(user)
    alias.enabled = False
    alias.expiry_date = arrow.now().shift(hours=-1)
    alias.expiry_action = AliasExpiryAction.Disable
    Session.commit()

    cron.process_expired_aliases()

    assert alias.expiry_date is not None


def test_process_expired_aliases_skips_already_trashed(flask_client):
    user = create_new_user()
    alias = Alias.create_new_random(user)
    alias.delete_on = arrow.now()
    alias.expiry_date = arrow.now().shift(hours=-1)
    alias.expiry_action = AliasExpiryAction.DeleteToTrash
    Session.commit()

    cron.process_expired_aliases()

    assert alias.expiry_date is not None


def test_process_expired_aliases_ignores_no_expiry(flask_client):
    user = create_new_user()
    alias = Alias.create_new_random(user)
    Session.commit()

    cron.process_expired_aliases()

    assert alias.enabled is True


@mail_sender.store_emails_test_decorator
def test_process_expired_aliases_sends_notification(flask_client):
    user = create_new_user()
    alias = Alias.create_new_random(user)
    alias.expiry_date = arrow.now().shift(hours=-1)
    alias.expiry_action = AliasExpiryAction.Disable
    alias.expiry_notify_user = True
    Session.commit()

    cron.process_expired_aliases()

    emails = mail_sender.get_stored_emails()
    assert len(emails) == 1
    assert user.email in emails[0].to


@mail_sender.store_emails_test_decorator
def test_process_expired_aliases_no_notification_when_opted_out(flask_client):
    user = create_new_user()
    alias = Alias.create_new_random(user)
    alias.expiry_date = arrow.now().shift(hours=-1)
    alias.expiry_action = AliasExpiryAction.Disable
    alias.expiry_notify_user = False
    Session.commit()

    cron.process_expired_aliases()

    emails = mail_sender.get_stored_emails()
    assert len(emails) == 0
