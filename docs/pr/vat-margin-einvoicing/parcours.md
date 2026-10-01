# Parcours : TVA sur marge et facture électronique

**Problème.** Dès qu'une taxe de TVA sur marge est active, plus aucune facture
client ne se valide (backoffice, site, point de vente). Le module de facture
électronique d'Akretion refuse toute taxe de TVA qui n'est pas calculée en
pourcentage, même si la facture n'utilise pas la marge.

**Ce qui change.** Avec `l10n_fr_vat_on_margin_einvoicing`, une taxe marge bien
configurée (catégorie UNECE `E`, motif `VATEX-EU-D` pour les agences de
voyages) ne bloque plus rien. Dans la facture électronique, la vente sur marge
est déclarée exonérée, à 0 %, sur le prix payé par le client, avec la mention
légale du régime. L'écriture comptable ne change pas.

## Base

- Pile `moka16-einv` (Odoo 16, port 8071), base `zz-vatmargin-einv`, créée sans
  démo : `l10n_fr`, `l10n_fr_vat_on_margin`, `account_invoice_en16931`,
  `l10n_fr_account_tax_unece`, `l10n_fr_account_invoice_en16931`, `point_of_sale`.
- Dépôts montés : ce dépôt, `akretion/fr-einvoicing` 16.0,
  `OCA/community-data-files` 16.0 (l'image embarque une version sans motif
  d'exonération), `OCA/intrastat-extrastat` 16.0.
- Bibliothèque `factur-x>=6.7,<7` : la 7.x attend une structure de données que
  le module Akretion 16.0 ne produit pas (`KeyError: 'BG-4'`).
- Données : client « Office de Tourisme de Colmar », produits « Séjour
  découverte Alsace » (TVA sur marge 20 % TTC) et « Guide papier Route des
  vins » (TVA 20 %).

Surfaces : backoffice, point de vente. Site web hors périmètre : il passe par la
même validation de facture (`_post`) que les deux autres, et le monter demande
une boutique et un moyen de paiement.

Dimensions : facture 100 % marge, facture mixte (marge + TVA 20 %), marge nulle
et négative, remise et ligne à prix négatif, avoir par extourne, marge +
assurance exonérée, deux régimes de marge sur la même facture.

## Étapes

1. Donner aux taxes marge de vente le type UNECE `VAT` et la catégorie `S`,
   comme en production.
2. **Avant, backoffice** : facture brouillon de 2 séjours à 1 200 € (achat
   900 €) et 3 guides à 24 €, bouton *Confirmer*. Attendu : erreur « … configuré
   sur 'Pourcentage de la marge' … » pour les trois taxes marge
   (`backoffice-avant.png`).
3. **Avant, point de vente** : vendre un séjour à l'Office de Tourisme de Colmar,
   payer en espèces avec *Facture* coché. Attendu : la même erreur, aucune
   facture créée (`pdv-avant.png`).
4. Installer `l10n_fr_vat_on_margin_einvoicing`. Passer les taxes marge de vente
   en catégorie `E`, motif `VATEX-EU-D`.
5. **Après, backoffice** : même facture, *Confirmer*. Attendu : facture
   comptabilisée, 2 486,40 € (`backoffice-apres.png`).
6. **Après, point de vente** : même vente. Attendu : écran du reçu, commande en
   état « facturé » avec sa facture comptabilisée (`pdv-apres.png`).
7. Générer UBL, CII et Factur-X des cas listés sous « Dimensions », puis les
   valider avec `schematron.py` (Saxon local, schematrons livrés par factur-x).
   Attendu : 0 erreur sur les profils utilisés en production (Factur-X
   EXTENDED, EXTENDED-CTC-FR en UBL et en CII). Résultat : `schematron.txt`,
   fichiers dans `xml/`.

Résultat attendu chiffré, facture mixte : ventilation S 20 % sur 72,00 € (TVA
14,40 €) et E 0 % sur 2 400,00 € (TVA 0) avec `VATEX-EU-D` ; total HT déclaré
2 472,00 €, TVA déclarée 14,40 €, total 2 486,40 €. Note de taxe (`TXD`) :
`Régime particulier – Agences de voyages`.

## Constats de validation hors du module

Ils apparaissent aussi sur une facture ordinaire sans marge :

- adresses électroniques du vendeur et de l'acheteur absentes (BR-FR-12,
  BR-FR-13) : posées en production par `l10n_fr_einvoicing` ;
- motif d'exonération au niveau de la ligne : refusé par le profil EN16931
  strict, accepté par les profils EXTENDED. Une taxe exonérée ordinaire donne
  le même constat.

Avec deux motifs d'exonération sur une facture, chaque motif a sa ventilation
`E`, comme le fait déjà Akretion pour les taxes exonérées ordinaires. La règle
révisée 2026 (BR-FREXT-E-08rev) passe ; l'ancienne (E-08ini) émet un
avertissement.
