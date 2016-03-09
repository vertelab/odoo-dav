# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013-2016 Vertel AB (<http://www.vertel.se>).
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

from openerp import models, fields, api, _
from openerp.exceptions import except_orm, Warning, RedirectWarning

import logging
_logger = logging.getLogger(__name__)

from .caldav_node import node_model_calendar_collection

class document_directory(models.Model):
    _inherit = 'document.directory'

    calendar_collection = fields.Boolean('Calendar Collection',default=False)
    
    def get_node_class(self, cr, uid, ids, dbro=None, dynamic=False,                       context=None):
        if dbro is None:
            dbro = self.browse(cr, uid, ids, context=context)

        if dbro.calendar_collection:
            return node_model_calendar_collection
        else:
            return super(document_directory, self).get_node_class(cr, uid, ids, dbro=dbro, dynamic=dynamic,context=context)

    #~ def get_description(self, cr, uid, ids, context=None):
        #~ # TODO : return description of all calendars
        #~ return False


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
