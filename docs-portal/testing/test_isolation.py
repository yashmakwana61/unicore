#!/usr/bin/env python3
"""Structural safety checks for the Edicai test-only Compose configuration."""
from pathlib import Path
import re
import unittest

BASE=Path(__file__).resolve().parent
COMPOSE=(BASE/"compose.yaml").read_text()
CONF=(BASE/"odoo-docs.conf").read_text()

class TestIsolation(unittest.TestCase):
    def test_localhost_only_odoo(self):
        self.assertIn('127.0.0.1:',COMPOSE)
        self.assertNotIn('0.0.0.0:',COMPOSE)
        odoo=COMPOSE.split('  odoo:',1)[1].split('  gateway:',1)[0]
        self.assertNotIn('    ports:',odoo)
        gateway=COMPOSE.split('  gateway:',1)[1].split('\nnetworks:',1)[0]
        self.assertIn('127.0.0.1:',gateway)
    def test_database_not_published(self):
        self.assertEqual(COMPOSE.split('  database:',1)[1].split('  odoo:',1)[0].count('    ports:'),0)
    def test_distinct_volumes_and_db(self):
        self.assertIn('name: edicai_docs_testing',COMPOSE)
        self.assertIn('edicai_docs_test',COMPOSE)
        self.assertIn('edicai_docs_pgdata',COMPOSE)
        self.assertIn('edicai_docs_filestore',COMPOSE)
    def test_limits_and_internal_net(self):
        self.assertIn('mem_limit: 3g',COMPOSE)
        self.assertIn('mem_limit: 1g',COMPOSE)
        self.assertIn('internal: true',COMPOSE)
        self.assertIn('name: edicai_docs_lab_access',COMPOSE)
        self.assertIn('external: true',COMPOSE)
        database=COMPOSE.split('  database:',1)[1].split('  odoo:',1)[0]
        self.assertNotIn('      - access',database)
        odoo=COMPOSE.split('  odoo:',1)[1].split('  gateway:',1)[0]
        self.assertNotIn('      - access',odoo)
        self.assertIn('      - sandbox',odoo)
        gateway=COMPOSE.split('  gateway:',1)[1].split('\nnetworks:',1)[0]
        self.assertIn('      - access',gateway)
        self.assertIn('      - sandbox',gateway)
    def test_cron_and_db_manager(self):
        self.assertIn('max_cron_threads = 0',CONF)
        self.assertIn('list_db = False',CONF)
        self.assertIn('admin_passwd = False',CONF)
    def test_no_persisted_password(self):
        self.assertNotIn('PASSWORD: password',COMPOSE)

if __name__=="__main__":
    unittest.main()
