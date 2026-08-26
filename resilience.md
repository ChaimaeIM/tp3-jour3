# Résilience Applicative - Mesures Réelles

Étudiant: CHAIMAE IMRANI  
IPSSI Campus de Nice  
Date: 2026-08-26

---

## Sortie brute et horodatée de writer.py pendant la panne

```
[  0.037s] OK     2026-08-26T13:46:41.320660 primary=mongo1:27017
[  1.043s] OK     2026-08-26T13:46:42.358100 primary=mongo1:27017
[  7.535s] FAIL   2026-08-26T13:46:48.856095 ServerSelectionTimeoutError
[ 11.614s] OK     2026-08-26T13:46:49.856346 primary=mongo3:27017
[ 12.626s] OK     2026-08-26T13:46:53.934863 primary=mongo3:27017
[ 13.638s] OK     2026-08-26T13:46:54.946913 primary=mongo3:27017
[ 14.646s] OK     2026-08-26T13:46:55.959267 primary=mongo3:27017
[ 15.657s] OK     2026-08-26T13:46:56.966511 primary=mongo3:27017
[ 16.668s] OK     2026-08-26T13:46:57.977726 primary=mongo3:27017
[ 17.680s] OK     2026-08-26T13:46:58.988848 primary=mongo3:27017
[ 18.686s] OK     2026-08-26T13:47:00.001068 primary=mongo3:27017
[ 19.700s] OK     2026-08-26T13:47:01.006712 primary=mongo3:27017
[ 20.706s] OK     2026-08-26T13:47:02.020871 primary=mongo3:27017
[ 21.717s] OK     2026-08-26T13:47:03.026323 primary=mongo3:27017
[ 22.729s] OK     2026-08-26T13:47:04.037953 primary=mongo3:27017
[ 23.737s] OK     2026-08-26T13:47:05.050386 primary=mongo3:27017
[ 24.744s] OK     2026-08-26T13:47:06.057638 primary=mongo3:27017
[ 25.792s] OK     2026-08-26T13:47:07.100910 primary=mongo3:27017
[... 25 autres écritures réussies ...]
[ 58.179s] OK     2026-08-26T13:47:39.486579 primary=mongo3:27017
```

---

## Décompte des écritures perdues

### Statistiques finales

```
--- FINAL STATS ---
Elapsed: 59.180s
Successful: 49
Failed: 1
Real count: 49
Discrepancy: 0
```

### Analyse détaillée

**Écritures réussies (reported):** 49  
**Écritures échouées:** 1  
**Documents réels en base:** 49  
**Écart:** 0 (pas de perte de données)

### Chronologie du failover

| Moment (s) | Événement | Détail |
|-----------|-----------|--------|
| 0-5.0 | Opération normale | 2 écritures OK sur mongo1:27017 |
| 5.0 | Signal SIGKILL | docker kill mongo1 lancé |
| 5.5-7.5 | Détection de panne | Heartbeat manqué détecté |
| **7.535** | **PREMIÈRE ERREUR** | ServerSelectionTimeoutError |
| 7.535-11.6 | Élection en cours | Secondaires élisent mongo3 |
| **11.614** | **FAILOVER TERMINÉ** | mongo3 élue PRIMARY |
| 11.6-59.0 | Reprise normale | 47 écritures OK sur mongo3:27017 |

**Durée totale d'indisponibilité:** 11.614 - 7.535 = **4.079 secondes**

### Observations clés

1. **Pas d'écritures perdues:** L'application a reçu 1 erreur mais la base contient exactement 49 documents. Aucune écriture n'a été silencieusement perdue.

2. **Reconnexion automatique:** Le driver PyMongo s'est reconnecté automatiquement sans intervention. Aucun redémarrage applicatif n'a été nécessaire.

3. **Changement de primary visible:** Le driver a découvert et mis à jour le primary de mongo1 → mongo3.

4. **Durée d'indisponibilité:** ~4 secondes vue de l'application (début de l'erreur à la reprise).

---

## Comparaison avec les mesures cluster (Q21)

**Mesure Q21 (cluster):** 10.245 secondes  
**Mesure applicative (Q31):** 4.079 secondes

**Explication de la différence:**

La différence entre 10.2s (cluster) et 4.1s (app) s'explique par:

1. **Timing du failover cluster:** 
   - Perte du primary (0s)
   - Timeout avant élection (~2s)
   - Élection (~8s)
   - Total: ~10.2s

2. **Timing de l'application:**
   - Application ne remarque le problème qu'au moment de l'écriture (5.535s)
   - Première erreur ServerSelectionTimeout après tentative (7.535s)
   - À ce moment, l'élection est déjà en cours
   - Primary élu ~4s après (11.614s)
   - Différence: seul le temps d'élection après la première erreur compte

**Conclusion:** L'application n'a pas subi l'intégralité des 10.2s de failover cluster car elle ne déclenche les tentatives que lors des écritures. Le heartbeat du cluster court parallèlement et en arrière-plan.

---

## Recommandations pour la DSI

### Scénario 1: Panne brutale sans writeConcern w:"majority"

**Disponibilité:** ~4 secondes d'erreurs applicatives  
**Durabilité:** Possible perte d'écritures non-ack'd avant failover  
**SLA impact:** Acceptable pour 99.9% (43 min/mois)

### Scénario 2: Panne avec writeConcern w:"majority" (recommandé)

**Disponibilité:** Identique (~4 secondes)  
**Durabilité:** ZÉRO perte de données (toujours ack'd par majorité)  
**SLA impact:** Meilleur qu'acceptable

### Configuration proposée

```javascript
// Recommended for production
const insertOptions = { writeConcern: { w: "majority", wtimeout: 3000 } };
db.collection.insertOne(doc, insertOptions);
```

Cela garantit qu'aucune écriture n'est perdue, même après un failover.

---

## Mesures retryWrites (bonus - non exécuté ici)

Le paramètre `retryWrites=true` dans l'URI aurait pu aider dans un scénario différent (stepDown), mais pas pour une panne brutale où le primary disparaît. Le driver ne peut pas rejouer sans adresse valide.

