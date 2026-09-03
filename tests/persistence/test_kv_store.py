from ensemblinator.persistence import kv_store


def test_kv_set_get(tmp_path):
    db_path = tmp_path / "test.sqlite3"

    assert kv_store.kv_get(db_path, "foo", "bar") is None

    kv_store.kv_set(db_path, "foo", "bar", "baz")
    assert kv_store.kv_get(db_path, "foo", "bar") == "baz"
    kv_store.kv_set(db_path, "foo", "bar", "test")
    assert kv_store.kv_get(db_path, "foo", "bar") == "test"

    assert kv_store.kv_get(db_path, "other-job", "bar") is None
    assert kv_store.kv_get(db_path, "foo", "other-key") is None


def test_kv_delete(tmp_path):
    db_path = tmp_path / "test.sqlite3"

    kv_store.kv_set(db_path, "foo", "other-key", "other-val")

    kv_store.kv_set(db_path, "foo", "bar", "baz")
    kv_store.kv_delete(db_path, "foo", "bar")
    assert kv_store.kv_get(db_path, "foo", "bar") is None
    kv_store.kv_delete(db_path, "foo", "bar")
    assert kv_store.kv_get(db_path, "foo", "bar") is None

    assert kv_store.kv_get(db_path, "foo", "other-key") == "other-val"

    kv_store.kv_set(db_path, "foo", "bar", "baz")
    assert kv_store.kv_get(db_path, "foo", "bar") == "baz"


def test_kv_isolation(tmp_path):
    db_path = tmp_path / "test.sqlite3"

    kv_store.kv_set(db_path, "job-a", "key-a", "val-aa")
    kv_store.kv_set(db_path, "job-a", "key-b", "val-ab")
    kv_store.kv_set(db_path, "job-b", "key-a", "val-ba")
    kv_store.kv_set(db_path, "job-b", "key-b", "val-bb")
    assert kv_store.kv_get(db_path, "job-a", "key-a") == "val-aa"
    assert kv_store.kv_get(db_path, "job-a", "key-b") == "val-ab"
    assert kv_store.kv_get(db_path, "job-b", "key-a") == "val-ba"
    assert kv_store.kv_get(db_path, "job-b", "key-b") == "val-bb"


def test_special_chars(tmp_path):
    db_path = tmp_path / "test.sqlite3"

    kv_store.kv_set(
        db_path,
        r"job'`~!@#$%^&*()-_=+[{]}\|;:'\",<.>/?]",
        r"key'`~!@#$%^&*()-_=+[{]}\|;:'\",<.>/?]",
        r"val'`~!@#$%^&*()-_=+[{]}\|;:'\",<.>/?]",
    )
    assert (
        kv_store.kv_get(
            db_path,
            r"job'`~!@#$%^&*()-_=+[{]}\|;:'\",<.>/?]",
            r"key'`~!@#$%^&*()-_=+[{]}\|;:'\",<.>/?]",
        )
        == r"val'`~!@#$%^&*()-_=+[{]}\|;:'\",<.>/?]"
    )
    kv_store.kv_delete(
        db_path,
        r"job'`~!@#$%^&*()-_=+[{]}\|;:'\",<.>/?]",
        r"key'`~!@#$%^&*()-_=+[{]}\|;:'\",<.>/?]",
    )
    assert (
        kv_store.kv_get(
            db_path,
            r"job'`~!@#$%^&*()-_=+[{]}\|;:'\",<.>/?]",
            r"key'`~!@#$%^&*()-_=+[{]}\|;:'\",<.>/?]",
        )
        is None
    )
