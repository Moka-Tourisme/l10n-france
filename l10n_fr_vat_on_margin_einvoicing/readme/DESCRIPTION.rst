Makes the VAT on margin of ``l10n_fr_vat_on_margin`` compatible with the
EN16931 e-invoices of ``account_invoice_en16931`` (Factur-X, UBL).

Without this module, an active margin tax blocks the validation of every
customer invoice, since the e-invoicing check only accepts VAT taxes computed
as a percentage.

A margin scheme sale carries no VAT that the customer may see or deduct
(art. 297 E of the CGI). The e-invoice therefore declares it:

* in VAT category ``E`` (exempt), at a nil rate, with a nil VAT amount;
* on the amount the customer pays, for the invoice line and the VAT breakdown;
* with the VAT exemption reason of the margin scheme and its legal mention
  (art. 242 nonies A of annex II of the CGI), also stated once in the tax
  note of the invoice (subject code ``TXD``).

Each exemption reason gets its own exempt VAT breakdown, as the French
extended profiles expect: a trip under the margin scheme and an exempt
insurance on the same invoice give two breakdowns in category ``E``.

The accounting entries are unchanged: the margin VAT is still posted and
reported in the VAT return. Invoices without margin lines produce exactly the
same e-invoice as before.
