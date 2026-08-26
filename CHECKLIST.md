# Checklist Finale - TP Jour 3

**Étudiant:** CHAIMAE IMRANI  
**Campus:** IPSSI Nice  
**Date remise:** 2026-08-26

---

## Livrables Requis

### Partie Réponses

- [x] **reponses_jour3.md**
  - [x] Q1-Q33 : Commandes exactes + sorties observées
  - [x] R1 : Expérience 4ème nœud
  - [x] R2 : Réplication vs Sharding
  - [x] R3 : Réglage electionTimeoutMillis
  - [x] R4 : Chiffre honnête pour DSI

### Partie Mesures

- [x] **failover.md**
  - [x] Tableau 3 scénarios (arrêt propre, panne brutale, retour nœud)
  - [x] Délais mesurés chronomètre en main
  - [x] Nœuds élus documentés
  - [x] Analyse de chaque scénario

- [x] **resilience.md**
  - [x] Sortie brute horodatée writer.py (59 lignes)
  - [x] Décompte écritures perdues
  - [x] Comparaison Q21 vs Q31
  - [x] Chronologie complète du failover

### Partie Infrastructure

- [x] **docker-compose.rs.yml**
  - [x] 3 nœuds MongoDB correctement configurés
  - [x] Ports mappés (27017, 27018, 27019)
  - [x] Oplog 128 Mo spécifié
  - [x] Network rslab pour communication intra-conteneur

- [x] **init-rs.js**
  - [x] Replica Set 3 nœuds initialisé
  - [x] Priorités asymétriques (mongo1: 2, autres: 1)
  - [x] Format rs.initiate() valide

- [x] **writer.py**
  - [x] Application Python/PyMongo complète
  - [x] 1 document/sec
  - [x] Logging horodaté
  - [x] Gestion des erreurs
  - [x] Décompte final OK/FAIL

- [x] **watch_primary.py**
  - [x] Moniteur de changement PRIMARY
  - [x] Horodatage relatif
  - [x] Détection d'élection automatique

### Partie Documentation

- [x] **README.md**
  - [x] Résumé court professionnel
  - [x] Structure du TP
  - [x] Résultats clés en tableau
  - [x] Technologies utilisées
  - [x] Apprentissages pédagogiques

---

## Mesures Obtenues

### Failover (Q21, Q17)

| Scénario | Délai | Nœud élu |
|----------|-------|----------|
| Arrêt propre (stop) | 2.156s | mongo2 |
| Panne brutale (kill) | 10.245s | mongo3 |
| Retour avec priority takeover | 10.0s | mongo1 |

### Oplog (Q12)

- **Size:** 133,861,376 bytes
- **Count:** 29,470 entries
- **Avg size:** 4,538 bytes/op
- **Capacity:** ~29,573 ops = 1.6 min window

### Write Concern (Q26)

- w: "majority" → **SUCCÈS** (2/2 nœuds)
- w: 3 → **ÉCHEC** (seuls 2 disponibles)
- Document quand-même écrit (danger d'app retry)

### Résilience Applicative (Q31)

- **Successful writes:** 49
- **Failed writes:** 1 (ServerSelectionTimeoutError)
- **Real count:** 49
- **Discrepancy:** 0 (zéro perte)
- **Downtime:** 4.079 secondes

### SLA Compliance (Q22, R4)

- **Requirement:** 99.9% = 43 min/mois
- **Observed:** 10.2s per failover
- **4 failovers/mois:** ~41s/mois
- **Verdict:** COMPLIANT + Margin

---

## Configuration Finale

### Replica Set Status

```
rs0 [direct: other] test> rs.status().members.map(m => m.name + " " + m.stateStr).join(" | ")
mongo1:27017 PRIMARY | mongo2:27017 SECONDARY | mongo3:27017 SECONDARY
```

### Parameters

- **electionTimeoutMillis:** 10,000 ms
- **heartbeatIntervalMillis:** 2,000 ms
- **oplogSize:** 128 Mo
- **members:** 3 (mongo1: priority 2, mongo2/3: priority 1)

### Data Set

- **Database:** census
- **Collection:** zips
- **Documents:** 29,470 (US postal codes)
- **States:** 51 (including DC + territories)
- **Population:** 248,649,628

---

## État Final

- [x] Tous conteneurs arrêtés proprement (`docker compose down -v`)
- [x] Port 27017 libéré pour Jour 4
- [x] Zéro données sensibles en clair
- [x] Tous fichiers versionnables (pas de .env)

---

## Notes Pédagogiques

### Clés d'apprentissage validées

1. **Oplog:** Mécanisme journal circulaire pour réplication granulaire
2. **Failover:** Élection automatique avec quorum majoritaire
3. **Write Concern:** Garantie de durabilité vs latence
4. **Read Concern:** Fraîcheur des données (local vs majority)
5. **RetryWrites:** Rejoue en cas de stepDown, NOT pour crash cluster
6. **Quorum:** 3 nœuds = majorité 2 = tolère 1 panne max
7. **Idempotence:** Oplog stocke valeurs finales, pas les opérateurs

### Cas d'usage production

- **SLA 99.9%:** Achievable avec 3 nœuds + w:"majority"
- **Failover duration:** ~10s cluster, ~4s app-visible
- **Zero data loss:** Avec writeConcern configuration appropriée
- **Network tolerance:** electionTimeoutMillis tunable (10s default OK)

---

## Post-TP

### Bonus (non exécuté)

- B1: Arbitre + faux sentiment de sécurité
- B2: Membre caché + membre retardé (backup)
- B3: Authentification + keyFile
- B4: Rollback en vrai (network disconnect)

### Continuation (Jour 4)

- Sharding sur 3 shards
- Shard keys et data distribution
- Balancer et chunk migration

---

**Signature:** CHAIMAE IMRANI  
**Établissement:** IPSSI Campus de Nice  
**Statut:** LIVRÉ COMPLET

