# TP Jour 3 : Réplication et Haute Disponibilité MongoDB

**Auteur:** CHAIMAE IMRANI  
**Établissement:** IPSSI Campus de Nice  
**Module:** MIA4 - Conception et Intégration d'un SGBD NoSQL  
**Date:** 2026-08-26

---

## Résumé

Ce TP explore la haute disponibilité dans MongoDB via un Replica Set 3 nœuds. Les objectifs pratiques incluent le déploiement, la mesure de failover, la compréhension de l'oplog, et la validation de la résilience applicative sous panne.

---

## Structure

### Déploiement Infrastructure

- **docker-compose.rs.yml:** Configuration de 3 nœuds MongoDB (mongo1, mongo2, mongo3) sur ports 27017-27019
- **init-rs.js:** Script d'initialisation du Replica Set avec priorités asymétriques
- **Oplog:** 128 Mo, permettant ~1.6 minutes de fenêtre de réplication

### Mesures Principales

| Métrique | Valeur | Détail |
|----------|--------|--------|
| Failover propre (docker stop) | 2.156s | Primary peut prévenir le set |
| Failover brutal (docker kill) | 10.245s | Timeout d'élection + heartbeat |
| Indisponibilité applicative | 4.079s | Mesurée sur writer.py live |
| Écritures perdues | 0 | Avec configuration w:"majority" |
| electionTimeoutMillis | 10,000ms | Paramètre clé du failover |
| heartbeatIntervalMillis | 2,000ms | Fréquence du monitoring |

---

## Résultats Clés

### 1. Oplog et Granularité de Réplication

- **Oplog size:** 128 Mo, contenant 29,470 entrées (1 par document)
- **Taille moyenne:** 4,538 bytes/operation
- **Capacité:** ~29,573 opérations = 1.6 minutes de fenêtre
- **Implication:** Un secondary down > 1.6 min nécessite une sync initiale complète

### 2. Failover et Élection

**Arrêt propre (SIGTERM):**
- Primary notifie le set
- Secondaires élisent immédiatement un nouveau PRIMARY
- Délai: 2.156s

**Panne brutale (SIGKILL):**
- Aucune notification préalable
- Secondaires attendent le heartbeat timeout
- Élection démarre après ~2s (heartbeatIntervalMillis)
- Élection dure ~8s (electionTimeoutMillis)
- Délai total: 10.245s

### 3. Résilience Applicative

**Test de failover réel:**
- Application (writer.py) insère 1 doc/sec pendant panne
- Après 5.5s de panne, 1 erreur observée
- Failover détecté à 7.535s
- Reprise à 11.614s (4.079s d'indisponibilité)
- **Zéro écriture perdue** avec writeConcern w:"majority"

### 4. Quorum et Majorité

**3 nœuds:**
- Quorum = 2 nœuds
- Tolère 1 panne
- 2 pannes = **no quorum** → indisponible

**4 nœuds:**
- Quorum = 2 nœuds
- Tolère toujours 1 seule panne (2 pannes = quorum juste)
- **Ajouter un 4ᵉ nœud n'améliore pas la tolérance**
- Nécessiter 5 nœuds pour tolérer 2 pannes (quorum = 3)

---

## SLA - Conclusion

**Requirement:** 99.9% = 43 minutes/mois  
**Observed failover:** 10.245s (cluster), 4.079s (application)

**Capacité SLA:** 
- Même avec 4 failovers/mois: 4 × 10.245s ≈ 41s/mois
- Bien en deçà des 43 min tolérées

**Recommendation:** Le Replica Set 3 nœuds avec writeConcern w:"majority" respecte amplement le SLA 99.9% et garantit zéro perte de données.

---

## Fichiers Livrés

| Fichier | Contenu |
|---------|---------|
| `reponses_jour3.md` | Réponses détaillées Q1-Q33, réflexions R1-R4 |
| `failover.md` | Tableau des 3 scénarios de failover avec délais |
| `resilience.md` | Sortie brute writer.py, analyse écritures perdues |
| `docker-compose.rs.yml` | Configuration infrastructure 3 nœuds |
| `init-rs.js` | Script d'initialisation Replica Set |
| `writer.py` | Application de test en Python/PyMongo |
| `watch_primary.py` | Moniteur de changement PRIMARY en real-time |

---

## Commandes Clés Exécutées

```bash
# Déployer
docker compose -f docker-compose.rs.yml up -d
docker exec -i mongo1 mongosh < init-rs.js

# Vérifier état
docker exec mongo1 mongosh --quiet --eval 'rs.status()'
docker exec mongo1 mongosh --quiet --eval 'rs.conf()'

# Charger données (29,470 codes postaux US)
docker exec mongo1 mongoimport --db census --collection zips --file zips.json

# Tester failover
docker kill mongo1  # Panne brutale
docker stop mongo1  # Arrêt propre

# Tester résilience app
docker run --network rslab python:3.12-slim python writer.py "mongodb://mongo1:27017,...?replicaSet=rs0"

# Nettoyer
docker compose -f docker-compose.rs.yml down -v
```

---

## Technologies Utilisées

- **MongoDB 7.0** - SGBD NoSQL documentaire
- **Docker Compose** - Orchestration conteneurs
- **Python 3.12 + PyMongo 4.6** - Driver client
- **Replica Set** - Réplication synchrone avec élection

---

## Apprentissages Pédagogiques

1. **Oplog:** Journal circulaire de 128 Mo pour la réplication et resynchronisation
2. **Failover:** Processus d'élection automatique du primary après panne (10s timeout)
3. **Write Concern:** Garantie de durabilité (w:1 rapide mais risqué, w:"majority" sûr)
4. **Read Concern:** Contrôle de la fraîcheur des lectures (local vs majority)
5. **Quorum:** Majorité stricte requise pour élire un primary et accepter écritures
6. **RetryWrites:** Rejoue automatique des écritures en cas de stepDown (pas pour crash total)

---

**Durée TP:** 4 heures  
**Statut:** Complet

