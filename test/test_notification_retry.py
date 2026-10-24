from unittest.mock import Mock, patch

import pytest

from onesignal.api.default_api import DefaultApi
from onesignal.exceptions import ApiException
from onesignal.model.notification import Notification


@pytest.mark.parametrize('status', [429, 503])
@pytest.mark.parametrize('retry_after,expected_delay', [
    ('Fri, 01 Jan 2027 00:00:30 GMT', 30),
    ('Friday, 01-Jan-27 00:00:30 GMT', 30),
    ('Fri Jan  1 00:00:30 2027', 30),
    ('Thu, 31 Dec 2026 23:59:30 GMT', 0),
    ('7', 7),
    ('0', 0),
    ('not-a-date', 1),
    (None, 1),
], ids=['http-date', 'rfc850-date', 'asctime-date', 'past-date',
        'seconds', 'zero', 'malformed', 'absent'])
def test_public_retry_helper_honors_retry_after(status, retry_after, expected_delay):
    api = DefaultApi(api_client=Mock())
    key = '00000000-0000-4000-8000-000000000001'
    notification = Notification(
        app_id='00000000-0000-4000-8000-000000000000', idempotency_key=key
    )
    failure = ApiException(status=status)
    failure.headers = {} if retry_after is None else {'rEtRy-AfTeR': retry_after}
    response = object()
    keys = []

    def create_notice(message, **kwargs):
        keys.append(message.idempotency_key)
        assert kwargs == {'_return_http_data_only': False}
        if len(keys) == 1:
            raise failure
        return response, 200, {'Idempotent-Replayed': 'true'}

    with patch.object(api, 'create_notification', side_effect=create_notice), \
            patch('onesignal.helpers.time.time', return_value=1798761600), \
            patch('onesignal.helpers.time.sleep') as sleep:
        result = api.create_notification_with_retry(notification, max_retries=1)

    assert result.response is response
    assert result.was_replayed is True
    assert keys == [key, key]
    if expected_delay:
        sleep.assert_called_once_with(expected_delay)
    else:
        sleep.assert_not_called()
