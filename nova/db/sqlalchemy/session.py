# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
"""
Session Handling for SQLAlchemy backend
"""

import eventlet.patcher
eventlet.patcher.monkey_patch()

import eventlet.db_pool
import sqlalchemy.orm
import sqlalchemy.pool

import nova.exception
import nova.flags
import nova.log


FLAGS = nova.flags.FLAGS
LOG = nova.log.getLogger("nova.db.sqlalchemy")


try:
    import MySQLdb
except ImportError:
    MySQLdb = None


_ENGINE = None
_MAKER = None


def get_session(autocommit=True, expire_on_commit=False):
    """Return a SQLAlchemy session."""
    global _ENGINE, _MAKER

    if _MAKER is None or _ENGINE is None:
        _ENGINE = get_engine()
        _MAKER = get_maker(_ENGINE, autocommit, expire_on_commit)

    session = _MAKER()
    session.query = nova.exception.wrap_db_error(session.query)
    session.flush = nova.exception.wrap_db_error(session.flush)
    return session


def get_engine():
    """Return a SQLAlchemy engine."""
    connection_dict = sqlalchemy.engine.url.make_url(FLAGS.sql_connection)

    engine_args = {
        "pool_recycle": FLAGS.sql_idle_timeout,
        "echo": False,
    }

    if "sqlite" in connection_dict.drivername:
        engine_args["poolclass"] = sqlalchemy.pool.NullPool

    elif MySQLdb and "mysql" in connection_dict.drivername:
        LOG.info(_("Using mysql/eventlet db_pool."))
        # MySQLdb won't accept 'None' in the password field
        password = connection_dict.password or ''
        pool_args = {
            "db": connection_dict.database,
            "passwd": password,
            "host": connection_dict.host,
            "user": connection_dict.username,
            "min_size": FLAGS.sql_min_pool_size,
            "max_size": FLAGS.sql_max_pool_size,
            "max_idle": FLAGS.sql_idle_timeout,
        }
        creator = eventlet.db_pool.ConnectionPool(MySQLdb, **pool_args)
        engine_args["pool_size"] = FLAGS.sql_max_pool_size
        engine_args["pool_timeout"] = FLAGS.sql_pool_timeout
        engine_args["creator"] = creator.create

    return sqlalchemy.create_engine(FLAGS.sql_connection, **engine_args)


def get_maker(engine, autocommit=True, expire_on_commit=False):
    """Return a SQLAlchemy sessionmaker using the given engine."""
    return sqlalchemy.orm.sessionmaker(bind=engine,
                                       autocommit=autocommit,
                                       expire_on_commit=expire_on_commit)
