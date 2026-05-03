from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.core.security import get_current_user
from app.main import app


def test_health(client):
    assert client.get('/health').status_code == 200


def test_demo_query_exists(client):
    with patch('app.main.call_rag_lambda', new=AsyncMock(return_value={"answer": "ok"})):
        assert client.post('/api/demo/query', json={"query": "hp"}).status_code == 200


def test_protected_reject_missing_token(client):
    assert client.post('/chat/message', json={"content": "hi"}).status_code == 401
    assert client.get('/chat/1/history').status_code == 401


def test_empty_chat_message_returns_400(client):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=101, cognito_sub='sub-1', email=None, username='u1')
    assert client.post('/chat/message', json={"content": "   "}).status_code == 400


def test_smalltalk_does_not_call_lambda(client):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=55, cognito_sub='sub-55', email=None, username='u55')
    chat = SimpleNamespace(id=12, user_id=55, character='harry')
    user_msg = SimpleNamespace(id=1, chat_id=12, role='user', content='hello', trace_id='t', created_at='2026-01-01T00:00:00Z')
    ai_msg = SimpleNamespace(id=2, chat_id=12, role='assistant', content='hi', trace_id='t', created_at='2026-01-01T00:00:01Z')
    with patch(
        'app.repositories.chat_repository.get_or_create_chat', new=AsyncMock(return_value=chat)
    ), patch('app.repositories.message_repository.list_recent_messages', new=AsyncMock(return_value=[])), patch(
        'app.repositories.message_repository.add_message', new=AsyncMock(side_effect=[user_msg, ai_msg])
    ), patch('app.services.chat_service.call_rag_lambda', new=AsyncMock(side_effect=AssertionError('lambda should not be called'))), patch(
        'app.services.router_agent.decide_route', return_value=SimpleNamespace(route='smalltalk', reason='smalltalk', answer='Hi there')
    ):
        res = client.post('/chat/message', json={"content": "hello", "character": "harry"})
    assert res.status_code == 200


def test_persistence_flow_uses_local_user_id_and_history_order(client):
    authed_user = SimpleNamespace(id=77, cognito_sub='cognito-sub-77', email='u@test.dev', username='wizard')
    app.dependency_overrides[get_current_user] = lambda: authed_user

    chat = SimpleNamespace(id=11, user_id=77, character='harry')
    persisted = [
        SimpleNamespace(id=1, chat_id=11, role='user', content='Who?', trace_id='a', created_at='2026-01-01T00:00:00Z'),
        SimpleNamespace(id=2, chat_id=11, role='assistant', content='A', trace_id='a', created_at='2026-01-01T00:00:01Z'),
    ]

    with patch(
        'app.repositories.chat_repository.get_or_create_chat', new=AsyncMock(return_value=chat)
    ) as get_or_create_chat_mock, patch('app.repositories.message_repository.list_recent_messages', new=AsyncMock(return_value=[])), patch(
        'app.repositories.message_repository.add_message', new=AsyncMock(side_effect=persisted)
    ), patch('app.services.chat_service.call_rag_lambda', new=AsyncMock(return_value={"answer": "A"})) as lambda_mock, patch(
        'app.services.router_agent.rewrite_query_for_rag', new=AsyncMock(return_value='rewritten')
    ), patch('app.repositories.chat_repository.get_chat', new=AsyncMock(return_value=chat)), patch(
        'app.repositories.message_repository.list_messages_for_chat', new=AsyncMock(return_value=persisted)
    ):
        post = client.post('/chat/message', json={"content": "Who?", "character": "harry"})
        hist = client.get('/chat/11/history')

    assert post.status_code == 200
    assert hist.status_code == 200
    assert lambda_mock.await_count == 1
    assert get_or_create_chat_mock.await_args.args[1] == 77
    ids = [m['id'] for m in hist.json()['messages']]
    assert ids == sorted(ids)


def test_user_cannot_read_another_users_chat(client):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=10, cognito_sub='sub-10', email=None, username='u10')
    other_chat = SimpleNamespace(id=99, user_id=22, character='harry')
    with patch('app.repositories.chat_repository.get_chat', new=AsyncMock(return_value=other_chat)):
        res = client.get('/chat/99/history')
    assert res.status_code == 404
