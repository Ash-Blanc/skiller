import json

from app.tools.xquik_tool import XquikToolkit


class StubResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_xquik_toolkit_maps_profile(monkeypatch):
    def fake_get(url, headers, params, timeout):
        assert url == "https://xquik.com/api/v1/x/users/alice"
        assert headers == {"X-API-Key": "test-key"}
        assert params == {}
        assert timeout == 30
        return StubResponse(
            {
                "username": "alice",
                "name": "Alice",
                "description": "Builder",
                "followers": 42,
                "following": 7,
                "verified": True,
                "location": "Austin",
                "createdAt": "2026-01-01T00:00:00Z",
            }
        )

    monkeypatch.setattr("requests.get", fake_get)

    toolkit = XquikToolkit(api_key="test-key")
    profile = json.loads(toolkit.get_user_info("alice"))

    assert profile["username"] == "alice"
    assert profile["followers_count"] == 42
    assert profile["verified"] is True


def test_xquik_toolkit_maps_tweets(monkeypatch):
    def fake_get(url, headers, params, timeout):
        assert url == "https://xquik.com/api/v1/x/users/alice/tweets"
        assert headers == {"X-API-Key": "test-key"}
        assert params == {"includeReplies": "false", "pageSize": 1}
        assert timeout == 30
        return StubResponse(
            {
                "tweets": [
                    {
                        "id": "123",
                        "text": "hello",
                        "createdAt": "2026-01-01T00:00:00Z",
                        "retweetCount": 3,
                        "likeCount": 9,
                        "replyCount": 2,
                        "viewCount": 100,
                        "isReply": False,
                    }
                ],
                "has_next_page": False,
                "next_cursor": "",
            }
        )

    monkeypatch.setattr("requests.get", fake_get)

    toolkit = XquikToolkit(api_key="test-key")
    tweets = json.loads(toolkit.get_user_tweets("@alice", max_tweets=1))

    assert tweets == [
        {
            "id": "123",
            "text": "hello",
            "created_at": "2026-01-01T00:00:00Z",
            "retweet_count": 3,
            "like_count": 9,
            "reply_count": 2,
            "view_count": 100,
            "is_reply": False,
        }
    ]


def test_xquik_toolkit_maps_followings(monkeypatch):
    def fake_get(url, headers, params, timeout):
        assert url == "https://xquik.com/api/v1/x/users/alice/following"
        assert headers == {"X-API-Key": "test-key"}
        assert params == {"pageSize": 20}
        assert timeout == 30
        return StubResponse(
            {
                "users": [
                    {
                        "username": "bob",
                        "name": "Bob",
                        "description": "Engineer",
                        "verified": True,
                        "followers": 100,
                    },
                    {
                        "username": "carol",
                        "name": "Carol",
                        "description": "Designer",
                        "verified": False,
                        "followers": 50,
                    },
                ],
                "has_next_page": False,
                "next_cursor": "",
            }
        )

    monkeypatch.setattr("requests.get", fake_get)

    toolkit = XquikToolkit(api_key="test-key")
    followings = toolkit.get_user_followings("alice", max_users=2, verified_only=True)

    assert followings == [
        {
            "username": "bob",
            "name": "Bob",
            "description": "Engineer",
            "verified": True,
            "followers_count": 100,
        }
    ]


def test_xquik_toolkit_follows_empty_page_cursor(monkeypatch):
    calls = []

    def fake_get(url, headers, params, timeout):
        calls.append(params)
        if len(calls) == 1:
            return StubResponse(
                {
                    "tweets": [],
                    "has_next_page": True,
                    "next_cursor": "page-2",
                }
            )
        return StubResponse(
            {
                "tweets": [{"id": "123", "text": "hello"}],
                "has_next_page": False,
                "next_cursor": "",
            }
        )

    monkeypatch.setattr("requests.get", fake_get)

    toolkit = XquikToolkit(api_key="test-key")
    tweets = json.loads(toolkit.get_user_tweets("alice", max_tweets=1))

    assert tweets == [
        {
            "id": "123",
            "text": "hello",
            "created_at": "",
            "retweet_count": 0,
            "like_count": 0,
            "reply_count": 0,
            "view_count": 0,
            "is_reply": False,
        }
    ]
    assert calls == [
        {"includeReplies": "false", "pageSize": 1},
        {"includeReplies": "false", "pageSize": 1, "cursor": "page-2"},
    ]
