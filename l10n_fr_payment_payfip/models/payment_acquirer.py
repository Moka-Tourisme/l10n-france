import logging
import requests
import urllib.parse
from requests.exceptions import ConnectionError
from odoo.exceptions import ValidationError
from xml.etree import ElementTree
from odoo.http import request

from odoo import api, fields, models, _
from odoo.osv import expression

from ..controllers.main import PayFIPController

_logger = logging.getLogger(__name__)


class PayFIPAcquirer(models.Model):
    # region Private attributes
    _inherit = 'payment.acquirer'
    # endregion

    # region Default methods
    # endregion

    # region Fields declaration
    provider = fields.Selection(selection_add=[('payfip', 'PayFIP')], ondelete={
        'payfip': 'set default'})

    state = fields.Selection(selection_add=[('activation', 'Activation')], ondelete={
        'activation': 'set default'})

    journal_id = fields.Many2one('account.journal', store=True)

    payfip_customer_number = fields.Char(
        string="Customer number",
        required_if_provider='payfip',
    )

    payfip_form_action_url = fields.Char(
        string="Form action URL",
        required_if_provider='payfip',
    )

    payfip_base_url = fields.Char(
        string="Base URL",
        required_if_provider='payfip',
    )

    payfip_notification_url = fields.Char(
        string="Notification URL",
        required_if_provider='payfip'
    )

    payfip_redirect_url = fields.Char(
        string="Return URL",
        required_if_provider='payfip'
    )

    payfip_activation_mode = fields.Boolean(
        string="Activation mode",
        default=False,
    )

    # endregion

    # region Fields method
    # endregion

    # region Constrains and Onchange
    @api.constrains('payfip_customer_number')
    def _check_payfip_customer_number(self):
        self.ensure_one()
        if self.provider == 'payfip' and self.payfip_customer_number not in ['dummy', '']:
            webservice_enabled, message = self._payfip_check_web_service()
            if not webservice_enabled:
                raise ValidationError(message)
            else:
                return True

    # endregion

    # region CRUD (overrides)
    # endregion
    @api.model
    def _get_compatible_acquirers(
            self, company_id, partner_id, currency_id=None, force_tokenization=False,
            is_validation=False, **kwargs
    ):
        # Compute the base domain for compatible acquirers
        domain = ['&', ('state', 'in', ['enabled', 'test', 'activation']), ('company_id', '=', company_id)]

        # Handle partner country
        partner = self.env['res.partner'].browse(partner_id)
        if partner.country_id:  # The partner country must either not be set or be supported
            domain = expression.AND([
                domain,
                ['|', ('country_ids', '=', False), ('country_ids', 'in', [partner.country_id.id])]
            ])

        # Handle tokenization support requirements
        if force_tokenization or self._is_tokenization_required(**kwargs):
            domain = expression.AND([domain, [('allow_tokenization', '=', True)]])

        compatible_acquirers = self.env['payment.acquirer'].search(domain)
        return compatible_acquirers

    # region Actions
    # endregion

    # region Model methods
    def _get_soap_url(self):
        return "https://www.tipi-client.budget.gouv.fr/tpa/services/securite"

    def _get_soap_namespaces(self):
        return {
            'ns1': "http://securite.service.tpa.cp.finances.gouv.fr/services/mas_securite/"
                   "contrat_paiement_securise/PaiementSecuriseService"
        }

    def payfip_get_form_action_url(self):
        self.ensure_one()
        return '/payment/payfip/pay'

    def payfip_get_id_op_from_web_service(self, email, price, object, acquirer_reference):
        self.ensure_one()
        id_op = ''
        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        if self.state == 'enabled':
            saisie_value = 'W'
        elif self.state == 'activation':
            saisie_value = 'X'
        else:
            saisie_value = 'T'

        exer = fields.Datetime.now().year
        numcli = self.payfip_customer_number
        saisie = saisie_value
        urlnotif = self.payfip_notification_url
        urlredirect = self.payfip_redirect_url

        soap_body = '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" ' \
                    'xmlns:pai="http://securite.service.tpa.cp.finances.gouv.fr/services/mas_securite/' \
                    'contrat_paiement_securise/PaiementSecuriseService">'
        soap_body += """
                <soapenv:Header/>
                <soapenv:Body>
                    <pai:creerPaiementSecurise>
                        <arg0>
                            <exer>%s</exer>
                            <mel>%s</mel>
                            <montant>%s</montant>
                            <numcli>%s</numcli>
                            <objet>%s</objet>
                            <refdet>%s</refdet>
                            <saisie>%s</saisie>
                            <urlnotif>%s</urlnotif>
                            <urlredirect>%s</urlredirect>
                        </arg0>
                    </pai:creerPaiementSecurise>
                </soapenv:Body>
            </soapenv:Envelope>
            """ % (exer, email, price, numcli, object, acquirer_reference, saisie, urlnotif, urlredirect)
        try:
            response = requests.post(self._get_soap_url(), data=soap_body, headers={
                'content-type': 'text/xml'})
        except ConnectionError:
            return id_op

        root = ElementTree.fromstring(response.content)
        errors = self._get_errors_from_webservice(root)

        for error in errors:
            _logger.error(
                "An error occured during idOp negociation with PayFIP web service. Informations are: {"
                "code: %s, description: %s, label: %s, severity: %s}" % (
                    error.get('code'),
                    error.get('description'),
                    error.get('label'),
                    error.get('severity'),
                )
            )
            return id_op

        idop_element = root.find('.//idOp')
        id_op = idop_element.text if idop_element is not None else ''
        return id_op

    def payfip_get_result_from_web_service(self, idOp):
        data = {}
        soap_url = self._get_soap_url()
        soap_body = '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" ' \
                    'xmlns:pai="http://securite.service.tpa.cp.finances.gouv.fr/services/mas_securite/' \
                    'contrat_paiement_securise/PaiementSecuriseService">'
        soap_body += """
                <soapenv:Header/>
                <soapenv:Body>
                    <pai:recupererDetailPaiementSecurise>
                        <arg0>
                            <idOp>%s</idOp>
                        </arg0>
                    </pai:recupererDetailPaiementSecurise>
                </soapenv:Body>
            </soapenv:Envelope>
            """ % idOp

        try:
            soap_response = requests.post(soap_url, data=soap_body, headers={
                'content-type': 'text/xml'})
        except ConnectionError:
            return data

        root = ElementTree.fromstring(soap_response.content)
        errors = self._get_errors_from_webservice(root)
        for error in errors:
            _logger.error(
                "An error occured during idOp negociation with PayFIP web service. Informations are: {"
                "code: %s, description: %s, label: %s, severity: %s}" % (
                    error.get('code'),
                    error.get('description'),
                    error.get('label'),
                    error.get('severity'),
                )
            )
            data = {
                'code': error.get('code'),
            }
            return data

        response = root.find('.//return')
        if response is None:
            raise Exception(
                "No result found for transaction with idOp: %s" % idOp)

        resultrans = response.find('resultrans')
        if resultrans is None:
            raise Exception(
                "No result found for transaction with idOp: %s" % idOp)

        dattrans = response.find('dattrans')
        heurtrans = response.find('heurtrans')
        exer = response.find('exer')
        idOp = response.find('idOp')
        mel = response.find('mel')
        montant = response.find('montant')
        numcli = response.find('numcli')
        objet = response.find('objet')
        refdet = response.find('refdet')
        saisie = response.find('saisie')

        data = {
            'resultrans': resultrans.text if resultrans is not None else False,
            'dattrans': dattrans.text if dattrans is not None else False,
            'heurtrans': heurtrans.text if heurtrans is not None else False,
            'exer': exer.text if exer is not None else False,
            'idOp': idOp.text if idOp is not None else False,
            'mel': mel.text if mel is not None else False,
            'montant': montant.text if montant is not None else False,
            'numcli': numcli.text if numcli is not None else False,
            'objet': objet.text if objet is not None else False,
            'refdet': refdet.text if refdet is not None else False,
            'saisie': saisie.text if saisie is not None else False,
        }
        return data

    def _payfip_check_web_service(self):
        self.ensure_one()
        error = _("It would appear that the customer number entered is not valid or that the PayFIP contract is "
                  "not properly configured.")

        soap_url = self._get_soap_url()
        soap_body = """
                    <soapenv:Envelope %s %s>
                       <soapenv:Header/>
                       <soapenv:Body>
                          <pai:recupererDetailClient>
                             <arg0>
                                <numCli>%s</numCli>
                             </arg0>
                          </pai:recupererDetailClient>
                       </soapenv:Body>
                    </soapenv:Envelope>
                    """ % (
            'xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"',
            'xmlns:pai="http://securite.service.tpa.cp.finances.gouv.fr/services/mas_securite/'
            'contrat_paiement_securise/PaiementSecuriseService"',
            self.payfip_customer_number
        )

        try:
            soap_response = requests.post(soap_url, data=soap_body, headers={
                'content-type': 'text/xml'})

        except ConnectionError:
            return False, error

        root = ElementTree.fromstring(soap_response.content)
        fault = root.find(
            './/S:Fault', {'S': 'http://schemas.xmlsoap.org/soap/envelope/'})

        if fault is not None:
            error_desc = fault.find('.//descriptif')
            if error_desc is not None:
                error += _("\nPayFIP server returned the following error: \"%s\"") % error_desc.text
            return False, error

        return True, ''

    def _get_errors_from_webservice(self, root):
        errors = []

        namespaces = self._get_soap_namespaces()
        error_functionnal = root.find('.//ns1:FonctionnelleErreur', namespaces)
        error_dysfonctionnal = root.find(
            './/ns1:TechDysfonctionnementErreur', namespaces)
        error_unavailabilityl = root.find(
            './/ns1:TechIndisponibiliteErreur', namespaces)
        error_protocol = root.find('.//ns1:TechProtocolaireErreur', namespaces)

        if error_functionnal is not None:
            code = error_functionnal.find('code')
            label = error_functionnal.find('libelle')
            description = error_functionnal.find('descriptif')
            severity = error_functionnal.find('severite')
            errors += [{
                'code': code.text if code is not None else 'NC',
                'label': label.text if label is not None else 'NC',
                'description': description.text if description is not None else 'NC',
                'severity': severity.text if severity is not None else 'NC',
            }]
        if error_dysfonctionnal is not None:
            code = error_dysfonctionnal.find('code')
            label = error_dysfonctionnal.find('libelle')
            description = error_dysfonctionnal.find('descriptif')
            severity = error_dysfonctionnal.find('severite')
            errors += [{
                'code': code.text if code is not None else 'NC',
                'label': label.text if label is not None else 'NC',
                'description': description.text if description is not None else 'NC',
                'severity': severity.text if severity is not None else 'NC',
            }]
        if error_unavailabilityl is not None:
            code = error_unavailabilityl.find('code')
            label = error_unavailabilityl.find('libelle')
            description = error_unavailabilityl.find('descriptif')
            severity = error_unavailabilityl.find('severite')
            errors += [{
                'code': code.text if code is not None else 'NC',
                'label': label.text if label is not None else 'NC',
                'description': description.text if description is not None else 'NC',
                'severity': severity.text if severity is not None else 'NC',
            }]
        if error_protocol is not None:
            code = error_protocol.find('code')
            label = error_protocol.find('libelle')
            description = error_protocol.find('descriptif')
            severity = error_protocol.find('severite')
            errors += [{
                'code': code.text if code is not None else 'NC',
                'label': label.text if label is not None else 'NC',
                'description': description.text if description is not None else 'NC',
                'severity': severity.text if severity is not None else 'NC',
            }]

        return errors

    # endregion

    def get_base_url(self):
        # Give priority to url_root to handle multi-website cases
        if request and request.httprequest.url_root:
            return request.httprequest.url_root
        return super().get_base_url()
