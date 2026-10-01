Nothing is written in the database when the module is installed. Each sale tax
of the margin scheme must be configured by hand, in *Invoicing > Configuration >
Taxes*:

* **UNECE Tax Type**: ``VAT``;
* **UNECE Tax Category**: ``E`` (Exempt from tax);
* **VAT Exemption Reason**, according to the margin scheme:

  * ``VATEX-EU-D``: travel agents ("Régime particulier – Agences de voyages");
  * ``VATEX-EU-F``: second-hand goods;
  * ``VATEX-EU-I``: works of art;
  * ``VATEX-EU-J``: collector's items and antiques.

The *VAT on Margin* option and the *Margin Percentage* computation go
together: a tax with only one of them is refused.

As long as a margin tax keeps another category or reason, invoice validation is
refused with a message naming the tax to fix.
