from __future__ import annotations

import os
import sys
import tempfile
import types
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
API_DIR = ROOT / "backend" / "api"
API_SRC_DIR = API_DIR / "src"
DB_SRC_DIR = ROOT / "backend" / "database" / "src"

for candidate in (str(API_DIR), str(API_SRC_DIR), str(DB_SRC_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)


class FakeWaiter:
    def wait(self, **_: object) -> None:
        return


class FakeDynamoTable:
    def __init__(self, store: dict[str, dict[str, dict[str, object]]], table_name: str) -> None:
        self._store = store
        self._table_name = table_name

    def get_item(self, *, Key: dict[str, str]) -> dict[str, object]:
        table = self._store.setdefault(self._table_name, {})
        item = table.get(Key["owner_user_id"])
        return {"Item": item} if item is not None else {}

    def put_item(self, *, Item: dict[str, object]) -> dict[str, object]:
        table = self._store.setdefault(self._table_name, {})
        table[str(Item["owner_user_id"])] = Item
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}


class FakeDynamoClient:
    class exceptions:
        class ResourceNotFoundException(Exception):
            pass

    def __init__(self, store: dict[str, dict[str, dict[str, object]]]) -> None:
        self._store = store

    def describe_table(self, *, TableName: str) -> dict[str, object]:
        if TableName not in self._store:
            raise self.exceptions.ResourceNotFoundException(TableName)
        return {"Table": {"TableName": TableName}}

    def create_table(self, *, TableName: str, **_: object) -> dict[str, object]:
        self._store.setdefault(TableName, {})
        return {"TableDescription": {"TableName": TableName}}

    def get_waiter(self, _: str) -> FakeWaiter:
        return FakeWaiter()


class FakeDynamoResource:
    def __init__(self) -> None:
        self.tables: dict[str, dict[str, dict[str, object]]] = {}
        self.meta = types.SimpleNamespace(client=FakeDynamoClient(self.tables))

    def Table(self, table_name: str) -> FakeDynamoTable:
        return FakeDynamoTable(self.tables, table_name)

    def reset(self) -> None:
        self.tables.clear()


FAKE_DYNAMO_RESOURCE = FakeDynamoResource()


def install_fake_boto3() -> None:
    fake_module = types.ModuleType("boto3")
    fake_module.resource = lambda service_name, **kwargs: FAKE_DYNAMO_RESOURCE
    sys.modules["boto3"] = fake_module


def reset_fake_environment() -> None:
    install_fake_boto3()
    FAKE_DYNAMO_RESOURCE.reset()
    os.environ["DYNAMODB_TABLE_NAME"] = "test-workspaces"
    os.environ["DYNAMODB_AUTO_CREATE"] = "true"
    os.environ["DEFAULT_AWS_REGION"] = "us-east-1"
    os.environ["APP_ENV"] = "test"
    os.environ["DYNAMODB_USE_LOCAL"] = "true"
    os.environ["DYNAMODB_USE_REMOTE"] = "false"
    os.environ["DYNAMODB_FALLBACK_TO_FILE"] = "true"
    os.environ["LOCAL_STATE_PATH"] = str(Path(tempfile.gettempdir()) / f"supplychain-ai-test-{uuid4().hex}.json")
    os.environ["OPENAI_API_KEY"] = ""
    os.environ["RESEND_API_KEY"] = ""
    os.environ["SMTP_HOST"] = ""
