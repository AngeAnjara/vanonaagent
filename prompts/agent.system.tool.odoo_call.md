### odoo_call:

**Prerequisites**: This tool requires Odoo integration to be enabled and configured in Settings. If you receive an error about Odoo not being enabled, inform the user to configure their Odoo connection in **Settings > Odoo Integration**.

⚠️ **Compatibilité des versions** : Les noms de champs et de modèles peuvent varier entre les versions d'Odoo (14, 15, 16, 17, etc.). Utilisez toujours `discover_fields` pour vérifier les champs disponibles avant de faire des requêtes complexes.
Connecte l'agent à une instance Odoo via l'API XML-RPC pour interroger les données métier (ventes, clients, produits, etc.).
Peut appeler des méthodes Odoo comme 'search', 'search_read', 'read', 'read_group', 'create', 'write'.

Arguments:
- model: Nom du modèle Odoo (ex: 'sale.order', 'res.partner', 'product.product')
- method: Méthode à appeler (ex: 'search_read', 'read_group')
- domain: Liste de filtres Odoo (ex: [["date_order", ">=", "2024-01-01"]])
- fields: Liste des champs à retourner (ex: ["name", "amount_total", "state"]).
- options: Dictionnaire d'options supplémentaires.
  - Pour `search` / `search_read`: `limit`, `offset`, `order`.
  - Pour `read`: `fields` (si non passé au niveau racine).
  - Pour `read_group`: `fields`, `groupby` (obligatoires), `limit`, `offset`, `orderby`, `lazy`, `context`.

Notes:
- Les domaines Odoo sont des listes de conditions.
- Les dates doivent être au format ISO (YYYY-MM-DD).
- Limitez les résultats pour éviter de surcharger le contexte.
- Pour `read_group`, utilisez toujours `orderby` (et non `order`) pour définir le tri.
- Pour `read_group`, `groupby` est obligatoire dans `options`.
- Exemples de groupby temporels: `"date_order:day"`, `"date_order:month"`, `"date_order:year"`.
- Exemples d'agrégations: `"amount_total:sum"`, `"amount_total:avg"`, `"id:count"`.

### Découverte des modèles disponibles

- Les modèles disponibles dans Odoo dépendent des modules installés et de la version.
- Avant d'utiliser un modèle métier spécifique, il est recommandé de vérifier qu'il existe dans votre instance.
- Pour lister les modèles disponibles, utilisez le modèle système `ir.model` avec `search_read`.

Exemple pour découvrir les modèles métier disponibles:

~~~json
{
  "thoughts": ["Je dois d'abord découvrir quels modèles sont disponibles"],
  "headline": "Liste des modèles Odoo disponibles",
  "tool_name": "odoo_call",
  "tool_args": {
    "model": "ir.model",
    "method": "search_read",
    "domain": [["transient", "=", false]],
    "fields": ["model", "name"],
    "options": {"limit": 200, "order": "name asc"}
  }
}
~~~

~~~json
{
  "thoughts": ["Lister les factures clients"],
  "headline": "Liste des factures",
  "tool_name": "odoo_call",
  "tool_args": {
    "model": "account.move",
    "method": "search_read",
    "domain": [["move_type", "=", "out_invoice"]],
    "fields": ["name", "partner_id", "amount_total", "state", "move_type", "invoice_date"],
    "options": {"limit": 50, "order": "invoice_date desc"}
  }
}
~~~

Vous pouvez également demander à l'outil de retourner une liste de modèles métier filtrés et mise en cache en utilisant le drapeau `discover_models` :

~~~json
{
  "thoughts": ["Je veux une liste rapide des modèles métier courants"],
  "headline": "Découverte automatique des modèles métier",
  "tool_name": "odoo_call",
  "tool_args": {
    "model": "ir.model",
    "method": "search_read",
    "discover_models": true
  }
}
~~~

### Modèles standards courants

- **Ventes**: `sale.order` (Commandes), `sale.order.line` (Lignes de commande)
- **Achats**: `purchase.order` (Bons de commande)
- **Comptabilité**: `account.move` (Factures/Écritures), `account.move.line` (Lignes comptables), `account.payment` (Paiements)
- **Contacts**: `res.partner` (Contacts/Clients/Fournisseurs)
- **Produits**: `product.product` (Produits), `product.template` (Modèles de produits)
- **Stock**: `stock.picking` (Transferts), `stock.move` (Mouvements de stock)
- **CRM**: `crm.lead` (Opportunités/Leads)
- **Projets**: `project.project` (Projets), `project.task` (Tâches)
- **RH**: `hr.employee` (Employés), `hr.leave` (Congés)

⚠️ Si vous recevez une erreur indiquant qu'un modèle « n'existe pas » (par exemple `account.financial.report`), vérifiez d'abord que le module correspondant est installé dans Odoo, ou utilisez `ir.model` comme ci-dessus pour découvrir les modèles disponibles.

#### ⚠️ Champs obsolètes et leurs remplacements (Odoo 16+)

| Modèle          | Ancien champ (≤15) | Nouveau champ (16+) |
|-----------------|--------------------|---------------------|
| `account.account` | `user_type_id`   | `account_type`      |
| `account.account` | `type`           | `account_type`      |
| `res.partner`     | `type`           | `company_type`      |

Si vous recevez une erreur "Invalid field", utilisez `discover_fields` pour obtenir la liste à jour des champs disponibles.

### Découverte des champs disponibles

Les champs disponibles sur un modèle varient selon la version d'Odoo et les modules installés.
Utilisez `discover_fields` pour interroger la structure d'un modèle avant d'écrire des requêtes complexes ou après une erreur "Invalid field".

Exemple pour découvrir les champs du modèle `account.account` :

~~~json
{
  "thoughts": ["Je dois vérifier quels champs sont disponibles sur account.account"],
  "headline": "Découverte des champs du modèle account.account",
  "tool_name": "odoo_call",
  "tool_args": {
    "discover_fields": "account.account"
  }
}
~~~

La réponse contient les métadonnées complètes de chaque champ (type, libellé, requis, relation, etc.).

Vous pouvez ensuite utiliser ces informations pour construire une requête `search_read` adaptée à votre version d'Odoo.

**Example usage**:
~~~json
{
  "thoughts": ["J'ai besoin des ventes du jour"],
  "headline": "Ventes du jour",
  "tool_name": "odoo_call",
  "tool_args": {
    "model": "sale.order",
    "method": "search_read",
    "domain": [["date_order", ">=", "2025-11-14 00:00:00"], ["date_order", "<=", "2025-11-14 23:59:59"]],
    "fields": ["name", "partner_id", "amount_total", "state"],
    "options": {"limit": 50, "order": "date_order desc"}
  }
}
~~~

~~~json
{
  "thoughts": ["Regrouper les ventes par mois"],
  "headline": "Statistiques ventes par mois",
  "tool_name": "odoo_call",
  "tool_args": {
    "model": "sale.order",
    "method": "read_group",
    "domain": [["state", "in", ["sale", "done"]]],
    "options": {
      "fields": ["amount_total:sum"],
      "groupby": ["date_order:month"],
      "orderby": "date_order:month desc",
      "limit": 100
    }
  }
}
~~~

~~~json
{
  "thoughts": ["Lister les clients actifs"],
  "headline": "Liste des clients",
  "tool_name": "odoo_call",
  "tool_args": {
    "model": "res.partner",
    "method": "search_read",
    "domain": [["customer_rank", ">", 0]],
    "fields": ["name", "email", "phone"],
    "options": {"limit": 100}
  }
}
~~~

~~~json
{
  "thoughts": ["Lire une commande spécifique"],
  "headline": "Détails d'une commande",
  "tool_name": "odoo_call",
  "tool_args": {
    "model": "sale.order",
    "method": "read",
    "ids": [42],
    "fields": ["name", "amount_total", "state", "partner_id"]
  }
}
~~~
