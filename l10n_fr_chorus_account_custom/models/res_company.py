# Copyright 2017-2021 Akretion France (http://www.akretion.com)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import base64
import json
import logging
from datetime import datetime, timedelta

import requests
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError

logger = logging.getLogger(__name__)

try:
    from requests_oauthlib import OAuth2Session
except ImportError:
    logger.debug("Cannot import requests-oauthlib")



class ResCompany(models.Model):
    _inherit = "res.company"

    def chorus_get_piste_api_oauth_identifiers(self, raise_if_ko=False):
        """Inherit this method if you want to configure your Chorus certificates
        elsewhere or have per-company Chorus certificates"""
        self.ensure_one()
        # In oauth_id and oauth_secret, I want to add the database name at the end of the get method
        # because I want to be able to use the same Odoo server for several databases
        oauth_id = tools.config.get("chorus_api_oauth_id_" + self._cr.dbname)
        oauth_secret = tools.config.get("chorus_api_oauth_secret_" + self._cr.dbname)
        if not oauth_id:
            msg = _(
                "Missing key 'chorus_api_oauth_id' in Odoo server " "configuration file"
            )
            if raise_if_ko:
                raise UserError(msg)
            else:
                logger.warning(msg)
                return False
        if not oauth_secret:
            msg = _(
                "Missing key 'chorus_api_oauth_secret' in Odoo server "
                "configuration file"
            )
            if raise_if_ko:
                raise UserError(msg)
            else:
                logger.warning(msg)
                return False
        return (oauth_id, oauth_secret)
