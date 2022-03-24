#!/usr/bin/env python3
#
# Copyright (C) 2015, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute
# it and/or modify it under the terms of GPLv2


import hashlib
import os
import pytest
import sys

from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from unittest.mock import patch

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))  # noqa: E501
with patch('sqlalchemy.create_engine', return_value=create_engine("sqlite://")):
    import orm
import tools

test_data_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
test_last_dates_path = os.path.join(test_data_path, 'last_date_files')

EXPECTED_TABLE_NAMES = ['graph', 'log_analytics', 'storage']


@pytest.fixture(scope='function')
def create_and_teardown_db():
    orm.create_db()
    yield
    orm.Base.metadata.drop_all(orm.engine)


@pytest.fixture(scope='function')
def teardown_db():
    yield
    orm.Base.metadata.drop_all(orm.engine)


def test_create_db(teardown_db):
    # Check there is no tables available
    inspector = inspect(orm.engine)
    assert inspector.get_table_names() == []

    # Create the tables
    orm.create_db()

    # Validate the tables and their structure
    inspector = inspect(orm.engine)
    table_names = inspector.get_table_names()
    assert table_names == EXPECTED_TABLE_NAMES
    for table in table_names:
        assert [x['name'] for x in inspector.get_columns(table)] == ['md5', 'min_processed_date', 'max_processed_date']


def test_add_get_row(create_and_teardown_db):
    """Test the ORM is able to insert row into the different tables and retrieve them as a whole and individually as
    expected."""
    # Add several entries and validate them
    for table in [orm.Graph, orm.LogAnalytics, orm.Storage]:
        for id_ in range(3):
            md5 = hashlib.md5(f'{table.__tablename__}{id_}'.encode()).hexdigest()
            original_datetime = "2022-01-01T23:59:59.1234567Z"
            row = table(md5=md5, min_processed_date=original_datetime, max_processed_date=original_datetime)
            orm.add_row(row=row)
            row = orm.get_row(table=table, md5=md5)
            assert row
            assert row.md5 == md5
            assert row.min_processed_date == original_datetime
            assert row.max_processed_date == original_datetime

            # Update the row
            new_datetime = "1999-01-01T23:59:59.1234567Z"
            orm.update_row(table=table, md5=md5, min_date=new_datetime, max_date=new_datetime)
            row = orm.get_row(table=table, md5=md5)
            assert row.min_processed_date == new_datetime
            assert row.max_processed_date == new_datetime

        assert len(orm.get_all_rows(table=table)) == 3

    # Try to obtain a non-existing item
    assert orm.get_row(table=orm.Graph, md5="non-existing") is None


def test_add_ko(create_and_teardown_db):
    """Test the add_row function by attempting to insert a row with None values. The commit operation should raise an
    IntegrityError that must be caught."""
    row = orm.Graph(md5="test", min_processed_date=None, max_processed_date=None)
    assert orm.add_row(row=row) is False
    assert len(orm.get_all_rows(orm.Graph)) == 0


def test_get_rows_ko(create_and_teardown_db):
    orm.Base.metadata.drop_all(orm.engine)
    assert orm.get_row(table=orm.Graph, md5="") is False
    assert orm.get_all_rows(table=orm.Graph) is False


@patch('orm.session.commit', side_effect=IntegrityError)
def test_update_row_ko(create_and_teardown_db):
    assert orm.update_row(orm.Graph, md5="test", min_date="", max_date="") is False


@pytest.mark.parametrize('file_exists, file_size', [
    (True, 0),
    (True, 100),
    (False, 100),
])
@patch('orm.create_db')
@patch('orm.migrate_from_last_dates_file')
def test_check_integrity(mock_migrate, mock_create_db, create_and_teardown_db, file_exists, file_size):
    with patch('os.path.exists', return_value=file_exists):
        with patch('os.path.getsize', return_value=file_size):
            orm.check_database_integrity()
            mock_create_db.assert_called()
            if file_exists and file_size > 0:
                mock_migrate.assert_called()
            else:
                mock_migrate.assert_not_called()


def test_check_integrity_ko(teardown_db):
    with patch('os.path.exists'):
        with patch('os.path.getsize', return_value=100):
            with patch('orm.migrate_from_last_dates_file', side_effect=Exception):
                assert orm.check_database_integrity() is False


@pytest.mark.parametrize('last_dates_file_path', [
    (os.path.join(test_last_dates_path, 'last_dates.json')),
    (os.path.join(test_last_dates_path, 'last_dates_graph.json')),
    (os.path.join(test_last_dates_path, 'last_dates_log_analytics.json')),
    (os.path.join(test_last_dates_path, 'last_dates_storage.json')),
    (os.path.join(test_last_dates_path, 'last_dates_old.json')),
    (os.path.join(test_last_dates_path, 'last_dates_clean.json'))
])
def test_migrate_from_last_dates_file(last_dates_file_path, create_and_teardown_db):
    """Test the last_dates file migration functionality."""
    items = orm.get_all_rows(table=orm.Graph)
    assert len(items) == 0

    with patch('tools.last_dates_path', new=last_dates_file_path):
        test_file_contents = tools.load_dates_json()
        orm.migrate_from_last_dates_file()

    # Validate the contents of each table
    for table in [orm.Graph, orm.LogAnalytics, orm.Storage]:
        items = orm.get_all_rows(table=table)
        if table.__tablename__ in test_file_contents:
            assert len(items) == len(test_file_contents[table.__tablename__].keys())
