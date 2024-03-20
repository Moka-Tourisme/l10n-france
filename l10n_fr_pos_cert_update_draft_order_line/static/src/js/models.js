/*
    Copyright (C) 2023 - Today: GRAP (http://www.grap.coop)
    @author: Sylvain LE GAL (https://twitter.com/legalsylvain)
*/

odoo.define("l10n_fr_pos_cert_update_draft_order_line.models", function (require) {
    "use strict";

    var models = require('point_of_sale.models');

    models.PosModel = models.PosModel.extend({
        disallowLineQuantityChange() {
            return false;
        }
    });

});
