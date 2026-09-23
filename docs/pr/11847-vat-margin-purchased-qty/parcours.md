# Parcours : la TVA sur marge compte l'achat réel (#11847)

Base : `test-app` (service `odoo16`, port 8070), données de démo, en français,
taxe « TVA sur marge 20% TTC - Vente » sur un service acheté à un prestataire.

Surfaces : devis

1. Confirmer un devis de 31 personnes à 25 € (coût 18) et valider sa facture client.
2. Sur le bon d'achat généré, passer la quantité à 30.
   Attendu : la marge TTC de la ligne devient 775 - 18 x 30 = 235 et la TVA sur marge du devis 39,17 € (au lieu de 775 - 18 x 31).
3. Sur un devis sans bon d'achat, la marge reste calculée sur la quantité vendue.

Avant : devis S00037, bon d'achat à 33, marge et TVA calculées sur les 35 vendus (40,83 €).
Après : devis S00049, bon d'achat à 30, TVA calculée sur les 30 achetés (39,17 €).

Scripts : `parcours.py avant|apres <devis> <bon d'achat>`, `edit_po.py <bon d'achat> <ligne> <quantité>`.
