# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Odoo SA 
#    Copyright (C) 2013-2016 Vertel AB.
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

from openerp.addons.document_webdav_fast import nodes
from openerp.addons.document_webdav_fast.dav_fs import dict_merge2
from openerp.addons.document.document import nodefd_static
from openerp.tools.safe_eval import safe_eval
from datetime import datetime, timedelta, time
from time import strptime, mktime, strftime
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from openerp import models, fields, api, _

import logging
_logger = logging.getLogger(__name__)

import re

try:
    from icalendar import Calendar, Event, vDatetime, FreeBusy
except ImportError:
    raise Warning('icalendar library missing, pip install icalendar')

_NS_CALDAV = "urn:ietf:params:xml:ns:caldav"

class node_model_calendar_collection(nodes.node_res_obj):
    "The children of this node are all models that implement vevent.model"

    def _get_default_node(self):
        return node_calendar("default", self, self.context, 'res.partner')

    def _get_filter_nodes(self, cr):
        '''find all models that implement vevent.model'''
        fields_obj = self.context._dirobj.pool.get('ir.model.fields')
        fields_ids = fields_obj.search(cr, self.context.uid,
            [('name', '=', 'id'),
             ('model_id.model', '!=', 'vevent.model')])
        fields = fields_obj.browse(cr, self.context.uid, fields_ids)
        return [node_filter("m-%s" % _field.model_id.model, self,
                                 self.context, _field.model_id.model,
                                 _field.model_id.name)
                for _field in fields]

    def _get_filter_nodes_by_name(self, cr, ir_model=None):
        model_obj = self.context._dirobj.pool.get('ir.model')
        model_ids = model_obj.search(cr, self.context.uid,
                                     [('model', '=', ir_model)])
        model_data = model_obj.read(cr, self.context.uid, model_ids,
                                   ['model', 'name'])
        return [node_filter("m-%s" % ir_model, self,
                                 self.context, str(ir_model),
                                 _model['name'])
                for _model in model_data]

    def _child_get(self, cr, name=False, parent_id=False, domain=None):
        if name:
            if name.startswith('m-'):
                return self._get_filter_nodes_by_name(cr, name[2:])
            return [self._get_default_node()]

        return [self._get_default_node()] + \
            self._get_filter_nodes(cr)


class node_filter(nodes.node_class):
    "The children of this node are all custom filters of a given model."
    DAV_M_NS = {
        "DAV:": '_get_dav',
    }

    def __init__(self, path, parent, context, ir_model='res.partner',
                 displayname=''):
        super(node_filter, self).__init__(path, parent, context)
        self.mimetype = 'application/x-directory'
        #~ self.mimetype = 'text/calendar'
        self.create_date = parent.create_date
        self.ir_model = ir_model
        self.displayname = displayname

    def _get_default_node(self):
        return node_calendar("default", self, self.context, self.ir_model)

    def _get_filter_nodes(self, cr, filter_ids):
        filters_obj = self.context._dirobj.pool.get('ir.filters')
        filter_data = filters_obj.read(cr, self.context.uid, filter_ids,
                                       ['context', 'domain', 'name'])
        return [node_calendar("filtered-%s" % _filter['id'], self,
                                 self.context,
                                 self.ir_model, _filter['name'],
                                 _filter['domain'], _filter['id'])
                for _filter in filter_data]

    def _get_ttag(self, cr):
        return 'calendar-%d-%s' % (self.context.uid, self.ir_model)

    def get_dav_resourcetype(self, cr):
        return [('collection', 'DAV:')]

    def children(self, cr, domain=None):
        return self._child_get(cr, domain=domain)

    def child(self, cr, name, domain=None):
        res = self._child_get(cr, name, domain=domain)
        if res:
            return res[0]
        return None

    def _child_get(self, cr, name=False, parent_id=False, domain=None):
        if name:
            if name.startswith('filtered-'):
                return self._get_filter_nodes(cr, [int(name[9:])])
            return [self._get_default_node()]

        filters_obj = self.context._dirobj.pool.get('ir.filters')
        filter_ids = filters_obj.search(cr, self.context.uid,
            [('model_id', '=', self.ir_model),
             ('user_id', 'in', [self.context.uid, False])])
        return [self._get_default_node()] + \
            self._get_filter_nodes(cr, filter_ids)


class node_calendar(nodes.node_class):
    """This node contains events for all records of a given model.
    If a filter is given, the node contains only those records
    that match the filter."""
    DAV_PROPS = dict_merge2(nodes.node_dir.DAV_PROPS,
                           {"DAV:": ('supported-report-set',),
                            _NS_CALDAV: ('address-data',
                                          'supported-address-data',
                                          'max-resource-size',
                                          )})
    DAV_M_NS = {
                "DAV:": '_get_dav',
                _NS_CALDAV: '_get_caldav',
                }
    http_options = {'DAV': ['calendar']}

    def __init__(self, path, parent, context,
                 #~ ir_model='calendar.event', filter_name=None,
                 ir_model='res.partner', filter_name=None,
                 filter_domain=None, filter_id=None):
        super(node_calendar, self).__init__(path, parent, context)
        self.mimetype = 'application/x-directory'
        self.create_date = parent.create_date
        self.ir_model = ir_model
        self.filter_id = filter_id
        if filter_domain and self.filter_id:
            self.filter_domain = ['|',
                                  ('dav_filter_id', '=', self.filter_id)] + \
                                  safe_eval(filter_domain)
        else:
            self.filter_domain = []
        if filter_name:
            self.displayname = "%s filtered by %s" % (ir_model, filter_name)
        else:
            self.displayname = "%s" % path
        # TODO self.write_date = max(create_date) [sic!] of all partners

    def children(self, cr, domain=None):
        if not domain:
            domain = []
        return self._child_get(cr, domain=(domain + self.filter_domain), name=None)

    def child(self, cr, name, domain=None):
        if not domain:
            domain = []
        res = self._child_get(cr, name, domain=(domain + self.filter_domain))
        if res:
            return res[0]
        return None

    def _child_get(self, cr, name=False, parent_id=False, domain=None):
        children = []
        res_partner_obj = self.context._dirobj.pool.get(self.ir_model)
        #~ res_partner_obj = self.context._dirobj.pool.get('res.partner')
        if not domain:
            domain = []

        _logger.error('_child_get name = %s' % name)
        if name:
            domain.append(('name', '=', name))
        partner_ids = res_partner_obj.search(cr, self.context.uid, domain)

        for partner in res_partner_obj.browse(cr, self.context.uid,
                                              partner_ids):
            children.append(
                res_node_event(partner.name,
                                 self, self.context, partner,
                                 None, None, self.ir_model))
        return children

    def _get_ttag(self, cr):
        return 'calendar-%d-%s' % (self.context.uid, self.path)

    def get_dav_resourcetype(self, cr):
        return [('collection', 'DAV:'),
                ('calendar', _NS_CALDAV)]

    def _get_dav_supported_report_set(self, cr):
        return ("supported-report", "DAV:",
                ("report", "DAV:",
                 [("calendar-query", _NS_CALDAV),
                  ("calendar-multiget", _NS_CALDAV)]))

    def _get_caldav_calendar_description(self, cr):
        return self.displayname

    def _get_caldav_supported_calendar_data(self, cr):
        return ('calendar-data', _NS_CALDAV, None,
                    {'content-type': "text/calendar", 'version': "3.0"})

    def _get_caldav_max_resource_size(self, cr):
        return 65535

    def get_domain(self, cr, filter_node):
        '''
        Return a domain for the caldav filter

        :param cr: database cursor
        :param filter_node: the DOM Element of filter
        :return: a list for domain
        '''
        # TODO Check if some of the code of
        #  http://bazaar.launchpad.net/~aw/openerp-vertel/6.1/files/head:/caldav/
        #  can be recycled.
        #   webdav.py, _caldav_filter_domain()
        if not filter_node:
            return []
        if filter_node.localName != 'calendar-query':
            return []

        raise ValueError("filtering is not implemented")

    def create_child(self, cr, path, data=None):
        if not data:
            raise ValueError("Cannot create a event with no data")
        res_partner_obj = self.context._dirobj.pool.get(self.ir_model)
        uid = res_partner_obj.get_uid_by_event(data)
        partner_id = res_partner_obj.create(cr, self.context.uid,
                                            {'name': 'DUMMY_NAME',
                                             'id': uid,
                                             #~ 'event_filename': path,
                                             'dav_filter_id': self.filter_id})
        res_partner_obj.set_event(cr, self.context.uid, [partner_id], data)
        partner = res_partner_obj.browse(cr, self.context.uid, partner_id)
        return res_node_event(partner.event_filename, self, self.context,
                                partner, None, None, self.ir_model)


class res_node_event(nodes.node_class):
    "This node represents a single event"
    our_type = 'file'
    DAV_PROPS = {
                 "urn:ietf:params:xml:ns:caldav": (
                    'calendar-description',
                 )}

    DAV_PROPS_HIDDEN = {
                        "urn:ietf:params:xml:ns:caldav": (
                           'address-data',
                        )}

    DAV_M_NS = {
           "urn:ietf:params:xml:ns:caldav": '_get_caldav'}

    http_options = {'DAV': ['calendar']}

    def __init__(self, path, parent, context, res_obj=None, res_model=None,
                 res_id=None, ir_model=None):
        super(res_node_event, self).__init__(path, parent, context)
        #~ self.mimetype = 'text/calendar; charset=utf-8'
        self.mimetype = 'text/calendar'
        self.create_date = parent.create_date
        self.write_date = parent.write_date or parent.create_date
        self.displayname = None
        self.ir_model = ir_model

        self.res_obj = res_obj
        if self.res_obj:
            if self.res_obj.create_date:
                self.create_date = self.res_obj.create_date
            if self.res_obj.write_date:
                self.write_date = self.res_obj.write_date

    def open_data(self, cr, mode):
        return nodefd_static(self, cr, mode)

    def get_data(self, cr, fil_obj=None):
        _logger.error('get_data method. %s' % fil_obj)
        #~ raise Warning(self.res_obj)
        return self.res_obj.get_caldav_calendar()
        #~ return self.res_obj.get_ics_calendar().serialize()
        
        
        #~ return '''BEGIN:VEVENT
#~ SUMMARY:AxelCoolAllday
#~ UID:20@CalendarDemoTest-83
#~ ATTENDEE:CN=AxelCool
#~ CREATED:20160307T105532Z
#~ DTSTART;VALUE=DATE:20160303
#~ END:VEVENT
#~ '''
        #~ return self.res_obj.get_event().serialize()
        #~ return self.res_obj.to_ical()

    def _get_caldav_address_data(self, cr):
        return self.get_data(cr)

    def get_dav_resourcetype(self, cr):
        return ''

    def get_data_len(self, cr, fil_obj=None):
        data = self.get_data(cr, fil_obj)
        if data:
            return len(data)
        return 0

    def set_data(self, cr, data):
        self.res_obj.set_event(data)

    def _get_ttag(self, cr):
        return 'calendar-event-%s-%d' % (self.res_obj._name,
                                              self.res_obj.id)

    def rm(self, cr):
        uid = self.context.uid
        partner_obj = self.context._dirobj.pool.get(self.ir_model)
        return partner_obj.unlink(cr, uid, [self.res_obj.id])


class res_partner(models.Model):
    _inherit = "res.partner"

    #~ @api.one
    def get_caldav_calendar(self):
        _logger.error('get_caldav_calendar %s' % self.id)
        calendar = Calendar()

        exported_ics = []
        for event in reversed(self.env['calendar.event'].search([('partner_ids','in',self.id)])):
            temporary_ics = event.get_caldav_file(exported_ics, self)
            if temporary_ics:
                exported_ics.append(temporary_ics[1])
                calendar.add_component(temporary_ics[0])
                    
        tmpCalendar = calendar.to_ical()
        tmpSearch = re.findall('RRULE:[^\n]*\\;[^\n]*', tmpCalendar)
        
        for counter in range(len(tmpSearch)):
            tmpCalendar = tmpCalendar.replace(tmpSearch[counter], tmpSearch[counter].replace('\\;', ';', tmpSearch[counter].count('\\;')))
        
        return tmpCalendar

class calendar_event(models.Model):
    _inherit = 'calendar.event'

    @api.multi
    def get_caldav_file(self, events_exported, partner):
        """
        Returns iCalendar file for the event invitation.
        @param event: event object (browse record)
        @return: .ics file content
        """
        ics = Event()
        event = self[0]

        #~ raise Warning(self.env.cr.dbname)
        #~ The method below needs som proper rewriting to avoid overusing libraries.
        def ics_datetime(idate, allday=False):
            if idate:
                if allday:
                    return str(vDatetime(datetime.fromtimestamp(mktime(strptime(idate, DEFAULT_SERVER_DATETIME_FORMAT)))).to_ical())[:8]
                else:
                    return vDatetime(datetime.fromtimestamp(mktime(strptime(idate, DEFAULT_SERVER_DATETIME_FORMAT)))).to_ical() + 'Z'
            return False

        #~ try:
            #~ # FIXME: why isn't this in CalDAV?
            #~ import vobject
        #~ except ImportError:
            #~ return res

        #~ cal = vobject.iCalendar()
        
        #~ event = cal.add('vevent')
        if not event.start or not event.stop:
            raise osv.except_osv(_('Warning!'), _("First you have to specify the date of the invitation."))
        ics['summary'] = event.name
        if event.description:
            ics['description'] = event.description
        if event.location:
            ics['location'] = event.location
        if event.rrule:
            ics['rrule'] = event.rrule
            #~ ics.add('rrule', str(event.rrule), encode=0)
            #~ raise Warning(ics['rrule'])

        if event.alarm_ids:
            for alarm in event.alarm_ids:
                valarm = ics.add('valarm')
                interval = alarm.interval
                duration = alarm.duration
                trigger = valarm.add('TRIGGER')
                trigger.params['related'] = ["START"]
                if interval == 'days':
                    delta = timedelta(days=duration)
                elif interval == 'hours':
                    delta = timedelta(hours=duration)
                elif interval == 'minutes':
                    delta = timedelta(minutes=duration)
                trigger.value = delta
                valarm.add('DESCRIPTION').value = alarm.name or 'Odoo'
        if event.attendee_ids:
            for attendee in event.attendee_ids:
                attendee_add = ics.get('attendee')
                attendee_add = attendee.cn and ('CN=' + attendee.cn) or ''
                if attendee.cn and attendee.email:
                    attendee_add += ':'
                attendee_add += attendee.email and ('MAILTO:' + attendee.email) or ''
                
                ics.add('attendee', attendee_add, encode=0)
                
        if events_exported:
            event_not_found = True
            
            for event_comparison in events_exported:
                #~ raise Warning('event_comparison = %s ics = %s' % (event_comparison, ics))
                if str(ics) == event_comparison:
                    event_not_found = False
                    break
            
            if event_not_found:
                events_exported.append(str(ics))
                
                ics['uid'] = '%s@%s-%s' % (event.id, self.env.cr.dbname, partner.id)
                ics['created'] = ics_datetime(strftime(DEFAULT_SERVER_DATETIME_FORMAT))
                tmpStart = ics_datetime(event.start, event.allday)
                tmpEnd = ics_datetime(event.stop, event.allday)
                
                if event.allday:
                    ics['dtstart;value=date'] = tmpStart
                else:
                    ics['dtstart'] = tmpStart
                    
                if tmpStart != tmpEnd or not event.allday:
                    if event.allday:
                        ics['dtend;value=date'] = str(vDatetime(datetime.fromtimestamp(mktime(strptime(event.stop, DEFAULT_SERVER_DATETIME_FORMAT))) + timedelta(hours=24)).to_ical())[:8]
                    else:
                        ics['dtend'] = tmpEnd
                
                return [ics, events_exported]
            
        else:
            events_exported.append(str(ics))
            
            ics['uid'] = '%s@%s-%s' % (event.id, self.env.cr.dbname, partner.id)
            ics['created'] = ics_datetime(strftime(DEFAULT_SERVER_DATETIME_FORMAT))
            tmpStart = ics_datetime(event.start, event.allday)
            tmpEnd = ics_datetime(event.stop, event.allday)
            
            if event.allday:
                ics['dtstart;value=date'] = tmpStart
            else:
                ics['dtstart'] = tmpStart
                
            if tmpStart != tmpEnd or not event.allday:
                if event.allday:
                    ics['dtend;value=date'] = str(vDatetime(datetime.fromtimestamp(mktime(strptime(event.stop, DEFAULT_SERVER_DATETIME_FORMAT))) + timedelta(hours=24)).to_ical())[:8]
                else:
                    ics['dtend'] = tmpEnd
            
            return [ics, events_exported]

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4
