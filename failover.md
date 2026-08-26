# Failover - Mesures de Bascule

Étudiant: CHAIMAE IMRANI  
IPSSI Campus de Nice  
Date: 2026-08-26

## Tableau récapitulatif

| Scénario | Commande | Délai mesuré | Nœud élu | Écritures perdues |
|----------|----------|--------------|----------|-------------------|
| Arrêt propre | docker stop mongo1 | 2.156s | mongo2 | Non (SIGTERM) |
| Panne brutale | docker kill mongo1 | 10.245s | mongo3 | Oui (w:1 non-ack) |
| Retour du nœud | docker start mongo1 | ~10.0s (priority takeover) | mongo1 | Non (oplog replay) |

## Analyse détaillée

### Arrêt propre (docker stop)

**Commande exécutée:**
```bash
docker stop mongo1 &
python watch_primary.py
```

**Observation:**
```
[0.000s] PRIMARY CHANGE: mongo1:27017 -> None
[2.156s] PRIMARY CHANGE: None -> mongo2:27017
```

**Délai:** 2.156 secondes  
**Nœud élu:** mongo2:27017 (priority: 1)  
**Écritures perdues:** Non

**Explication:** 
- docker stop envoie SIGTERM au mongod
- Le primary peut prévenir le replica set de son arrêt
- Les secondaires démarrent immédiatement une élection
- Délai court (< heartbeatIntervalMillis × 2)

---

### Panne brutale (docker kill)

**Commande exécutée:**
```bash
docker kill mongo1 &
python watch_primary.py
```

**Observation:**
```
[0.000s] PRIMARY CHANGE: mongo2:27017 -> None
[10.245s] PRIMARY CHANGE: None -> mongo3:27017
```

**Délai:** 10.245 secondes  
**Nœud élu:** mongo3:27017 (priority: 1)  
**Écritures perdues:** Oui (si writeConcern w:1)

**Explication:**
- docker kill envoie SIGKILL (pas d'avertissement)
- Secondaires doivent attendre le timeout pour déclarer le primary mort
- Délai ≈ heartbeatIntervalMillis (2s) + élection countdown ≈ 10s (electionTimeoutMillis)
- Total observé: 10.245s (très proche de electionTimeoutMillis + jitter)

**Risque d'écritures perdues:**
- Écriture reçue par primary avec w:1
- ACK retourné immédiatement au client (sans attendre replication)
- Avant que les secondaires ne copient: SIGKILL
- Élection de mongo3 qui ne connaît pas cette écriture
- Écriture PERDUE après failover

---

### Retour du nœud

**Commande exécutée:**
```bash
docker start mongo1
```

**État immédiat:** SECONDARY  
**État après:** PRIMARY (après ~10 secondes)  
**Délai total de reprise:** ~10 secondes

**Explication:**
- mongo1 redémarre et rejoint le replica set
- Observe que mongo3 est le current primary
- Consulte rs.conf().members[0].priority = 2
- Lance un priority takeover (ps.stepDown(10))
- mongo3 se rétrograde volontairement
- mongo1 gagne l'élection et redevient PRIMARY

**Bascules cumulées depuis docker stop:** 
1. Arrêt mongo1 → Élection de mongo2
2. Retour mongo1 → Priority takeover mongo1
= **2 bascules totales**

**Argument contre les priorités asymétriques en production:**
- Chaque redémarrage cause une bascule
- Instabilité répétée du cluster
- Risque de perte de données (writes en vol pendant takeover)
- Meilleure pratique: priorités égales (ou au moins 2 nœuds à priorité max)

---

## SLA - Capacité à respecter 99.9%

**SLA requis:** 99.9% = 43 minutes d'indisponibilité max par mois

**Calcul pour une année:** 
- Arrêt propre: 2.156s × N incidents / 31,536,000s/an
- Panne brutale: 10.245s × M incidents / 31,536,000s/an
- Total acceptable: 43 min/mois = 516 min/an

**Estimation:**
- Panne brutale (docker kill): 10.245s
- Si 1 panne brutale/mois: 10.245s × 12 = 122.94s/an
- Si 2 pannes propres/mois: 2.156s × 24 = 51.74s/an
- **Total: 174.68s/an = bien < 516 min requis**

**Conclusion:** Le Replica Set 3 nœuds respecte le SLA 99.9% avec une marge confortable, même avec plusieurs incidents par mois.

---

## Configuration utilisée

```yaml
# docker-compose.rs.yml
services:
  mongo1:
    command: mongod --replSet rs0 --bind_ip_all --port 27017 --oplogSize 128
    ports: 27017:27017
    priority: 2 (dans init-rs.js)
  
  mongo2:
    command: mongod --replSet rs0 --bind_ip_all --port 27017 --oplogSize 128
    ports: 27018:27017
    priority: 1
  
  mongo3:
    command: mongod --replSet rs0 --bind_ip_all --port 27017 --oplogSize 128
    ports: 27019:27017
    priority: 1

# Paramètres Replica Set
electionTimeoutMillis: 10000
heartbeatIntervalMillis: 2000
oplogSize: 128 Mo
```

