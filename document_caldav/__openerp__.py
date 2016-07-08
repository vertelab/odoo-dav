# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2010-2013 OpenERP s.a. (<http://openerp.com>).
#    Copyright (C) 2013-2016 Vertel AB 
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
    "name": "CalDAV",
    "version": "0.1",
    "depends": ["base", "document_webdav_fast", "web"],
    'author': 'Vertel AB',
    "category": "",
    "summary": "A simple CalDAV implementation",
    'license': 'AGPL-3',
    "description": """
A very simple CalDAV implementation inspired of InitOS Carddav implementation
====================================

Urls:

- For a partners calendar: /webdav/$db_name/calendar/users/$login/a/$partner_name/

Collections can be filtered, the url is then shown in the search view drop-down.
# sudo pip install pywebdav
# sudo pip install icalendar
# document_webdav_fast from https://github.com/initOS/openerp-dav
    """,
    'data': [
        'caldav_setup.xml',
    ],
    'demo': [
    ],
    'external_dependenies': {'python': ['pywebdav','icalendar'],'bin': []},
    'test': [
    ],
    'installable': True,
    'auto_install': False,
    'js': ['static/src/js/search.js'],
    'qweb': ['static/src/xml/base.xml'],
}
