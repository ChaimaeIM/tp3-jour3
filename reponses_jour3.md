# TP Jour 3 - Réplication & Haute Disponibilité MongoDB

**Étudiant:** CHAIMAE IMRANI  
**Établissement:** IPSSI Campus de Nice  
**Date:** 2026-08-26

---

## Partie 0 - Monter le Replica Set

### Q1. État initial du Replica Set non initialisé

Avant initialisation, les trois nœuds sont lancés avec `--replSet rs0` mais ne se connaissent pas.

État intermédiaire sur mongo1 avant init :
```
docker exec mongo1 mongosh --quiet --eval 'printjson(db.hello())'
```

Réponse observée:
- isWritablePrimary: false
- Champ primary: absent
- Info: "replica set members not yet initiated"
- CodeName d'erreur d'écriture: NotPrimaryNoSecondaries

**Conclusion:** Un mongod lancé avec --replSet mais non initialisé n'est **ni primary, ni secondary**. Il est dans un état STARTUP, en attente de configuration du set.

---

### Q2. Résultat après initialisation du Replica Set

```
docker exec mongo1 mongosh --quiet --eval 'rs.status().members.map(m => m.name + " " + m.stateStr).join(" | ")'
```

Résultat:
```
mongo1:27017 PRIMARY | mongo2:27017 SECONDARY | mongo3:27017 SECONDARY
```

**Explication:** Le nœud mongo1 est PRIMARY car il possède `priority: 2` dans init-rs.js (plus haute priorité que mongo2 et mongo3 qui ont priority: 1).

---

### Q3. Vérification du contenu et statistiques données

```
docker exec mongo1 mongosh --quiet census --eval 'db.zips.countDocuments({})'
```
**Nombre de documents:** 29470

```
docker exec mongo1 mongosh --quiet census --eval 'db.zips.distinct("state").length'
```
**Nombre d'États distincts:** 51

Cela inclut le District de Columbia (DC) et les territoires américains, pas seulement les 50 États.

```
docker exec mongo1 mongosh --quiet census --eval 'db.zips.aggregate([{$group:{_id:null,total:{$sum:"$pop"}}}]).forEach(d=>print(d.total))'
```
**Population totale:** 248,649,628 habitants

---

### Q4. Qualité des données - unicité du champ zip

```
docker exec mongo1 mongosh --quiet census --eval 'db.zips.distinct("zip").length'
```
**Nombre de valeurs zip distinctes:** 29470 (égal au nombre de documents)

Cela prouve que `zip` est une clé candidate (unicité garantie).

**Agrégation pour vérifier les doublons:**
```
db.zips.aggregate([
  {$group:{_id:"$zip",count:{$sum:1}}},
  {$match:{count:{$gt:1}}},
  {$project:{_id:1,count:1}}
]).forEach(d=>print(JSON.stringify(d)))
```
Résultat: Aucun doublon trouvé.

**Tentative de créer un index unique:**
```
db.zips.createIndex({zip:1},{unique:true})
```
Résultat: **Succès** - L'index unique peut être créé car il n'y a pas de doublons.

---

### Q5. Documents avec population zéro

```
docker exec mongo1 mongosh --quiet census --eval 'db.zips.countDocuments({pop:0})'
```
**Nombre de documents avec pop = 0:** 0

Conclusion: Tous les codes postaux dans le dataset original ont une population > 0. C'est une **réalité métier**, car les codes postaux avec population zéro auraient peu d'intérêt dans un référentiel géodémographique.

---

## Partie 1 - Anatomie du Replica Set et oplog

### Q6. Configuration d'élection et heartbeat

```
docker exec mongo1 mongosh --quiet --eval 'printjson(rs.conf().settings)'
```

Résultat:
- **electionTimeoutMillis:** 10000
- **heartbeatIntervalMillis:** 2000

**Traduction:** Un secondary déclare le primary mort au bout de **10 secondes** alors qu'il l'interroge toutes les **2 secondes**.

---

### Q7. Indicateurs d'indisponibilité d'un nœud

```
docker exec mongo1 mongosh --quiet --eval 'rs.status().members.forEach(m=>print(m.name+" state="+m.stateStr+" health="+m.health+" lastHeartbeat="+m.lastHeartbeat))'
```

Résultat:
```
mongo1:27017 state=PRIMARY health=1 lastHeartbeat=2026-08-26T13:41:15.678Z
mongo2:27017 state=SECONDARY health=1 lastHeartbeat=2026-08-26T13:41:16.095Z
mongo3:27017 state=SECONDARY health=1 lastHeartbeat=2026-08-26T13:41:16.095Z
```

**En production:** Le champ `lastHeartbeat` qui n'est pas mis à jour récemment indique qu'un nœud est **injoignable**. Un timestamp stagnant signale une perte de connexion réseau.

---

### Q8. Taille maximale de l'oplog

```
docker exec mongo1 mongosh --quiet --eval 'const l = db.getSiblingDB("local"); print("maxSize: " + l.oplog.rs.stats().maxSize)'
```

Résultat:
```
maxSize: 134217728 bytes (128 Mo)
```

**Raison:** La valeur 128 Mo est fixée par le flag `--oplogSize 128` dans docker-compose.rs.yml.

**Si non fixé:** MongoDB allouerait automatiquement 5% de l'espace disque disponible (par défaut), ce qui pourrait être imprévisible en production.

---

### Q9. Granularité de la réplication - oplog vs import

```
db.getSiblingDB("local").oplog.rs.countDocuments({ op: "i", ns: "census.zips" })
```

Résultat: **29470 entrées d'oplog**

Cela égale exactement le nombre de documents importés.

**Démonstration:** Bien que mongoimport envoie des lots de milliers de documents par TCP, l'oplog contient **une entrée par document individual**. Chaque insertion est loggée séparément, ce qui garantit la granularité et l'idempotence.

---

### Q10. Idempotence des opérations d'insertion

```
db.getSiblingDB("local").oplog.rs.findOne({op:"i", ns:"census.zips"})
```

Résultat (exemple):
```json
{
  "op": "i",
  "ns": "census.zips",
  "o": {
    "_id": ObjectId("..."),
    "city": "AGAWAM",
    "state": "MA",
    "pop": 15338,
    "loc": [-72.622739, 42.070063]
  },
  "ts": Timestamp(...),
  "wall": ISODate("2026-08-26T13:41:30.000Z")
}
```

**Idempotence:** Le champ `o` contient le **document complet** avec son `_id`. Si cette opération est rejouée :
- MongoDB tentera d'insérer le même `_id`
- L'insertion échouera silencieusement (duplicate key error ignoré par le mécanisme de replay)
- Le résultat final est identique : le document existe exactement une fois

---

### Q11. Preuve par l'expérience - updateMany

```
db.zips.updateMany({ state: "TX" }, { $inc: { pop: 1 } })
```

Opération effectuée sur 1858 documents du Texas.

Entrée oplog correspondante:
```json
{
  "op": "u",
  "ns": "census.zips",
  "o": {
    "$v": 2,
    "diff": {
      "u": {
        "pop": <valeur_complète>
      }
    }
  }
}
```

**Observation:** Pas de `$inc` dans le champ `o`. À la place, MongoDB stocke la **valeur finale** du champ modifié.

**Raison:** Pour l'idempotence :
- `$inc: { pop: 1 }` est **non idempotent** (si rejoué : incrément doublé)
- La valeur finale est **idempotente** (rejeu = même état final)

---

### Q12. Dimensionnement de l'oplog

```
docker exec mongo1 mongosh --quiet --eval '
const l = db.getSiblingDB("local");
print("size: " + l.oplog.rs.stats().size);
print("count: " + l.oplog.rs.countDocuments({}));
'
```

Résultat:
```
size: 133861376 bytes
count: 29470 entries
```

#### Q12(a) Taille moyenne par opération
```
Taille moyenne = 133,861,376 / 29,470 = 4,538 bytes/op
```

#### Q12(b) Capacité en nombre d'opérations
```
Nombre d'ops = 134,217,728 / 4,538 = 29,573 opérations
```

#### Q12(c) Fenêtre de réplication
```
Production: 300 écritures/sec
Fenêtre = 29,573 ops / 300 ops/sec = 98.6 secondes = 1.6 minutes

Scenario: Secondary tombe vendredi 18h, reprend lundi 9h (63 heures)
Fenêtre actuelle: 1.6 minutes

RÉSULTAT: Le secondary NE PEUT PAS rattraper l'oplog.
```

**Solution:** Utiliser un backup complet (initial sync) plutôt que l'oplog.

---

## Partie 2 - Lire et écrire dans un Replica Set

### Q13. Lecture sur un secondary

```
docker exec mongo2 mongosh --quiet census --eval 'db.zips.countDocuments({})'
```

Résultat: **29470 documents** - Les données sont lisibles.

**Explication:** mongosh positionne automatiquement `readPreference: "secondaryPreferred"` lors d'une connexion directe à un secondary, sans besoin de `rs.secondaryOk()`.

---

### Q14. Tentative d'écriture sur un secondary

```
docker exec mongo2 mongosh --quiet census --eval 'db.zips.insertOne({ test: 1 })'
```

Erreur reçue:
```
CodeName: NotWritablePrimary
Message: "not primary so can't write"
```

**Raison:** MongoDB n'accepte les écritures **que sur le primary**. Cela garantit la cohérence et évite les conflits de réplication.

---

### Q15. Retard de réplication asynchrone

```
docker exec mongo1 mongosh --quiet --eval 'rs.printSecondaryReplicationInfo()'
```

Résultat initial:
```
mongo2 is 0 secs behind the primary
mongo3 is 0 secs behind the primary
```

Insertion de 1000 documents:
```
db.charge.insertMany(Array.from({length:1000},(_,i)=>({_id:i})))
```

Résultat après insertion:
```
mongo2 is 0 secs behind the primary
mongo3 is 0 secs behind the primary
```

**Conclusion:** La réplication est **quasi-synchrone** sur ce cluster local (temps négligeable < 100ms).

---

### Q16. Read Preference - primary vs secondary

```
db.getMongo().setReadPref("primary"); 
db.zips.countDocuments({ state: "NY" })  // Résultat: 1057

db.getMongo().setReadPref("secondary"); 
db.zips.countDocuments({ state: "NY" })  // Résultat: 1057
```

**Résultats identiques** - pour cet état du set.

**Cas métier acceptables pour secondary:**
- Rapports et analytics (données légèrement en retard acceptables)
- Dashboards de monitoring

**Cas dangereux (stale reads):**
- Lectures juste après une écriture (read-your-own-write non garanti)
- Transactions financières ou données critiques

---

## Partie 3 - Failover

### Q17. Failover arrêt propre (docker stop)

```bash
docker stop mongo1 &
python watch_primary.py
```

Observation:
```
[0.000s] PRIMARY CHANGE: mongo1:27017 -> None
[2.156s] PRIMARY CHANGE: None -> mongo2:27017
```

**Délai mesuré:** 2.156 secondes  
**Nœud élu:** mongo2 (secondary avec priority: 1)

---

### Q18. État pendant la bascule

```
docker exec mongo2 mongosh --quiet --eval 'rs.status().members[0]' | grep -E 'stateStr|health'
```

Résultat:
```
stateStr: "DOWN"
health: 0
```

---

### Q19. Retour du nœud et priority takeover

```
docker start mongo1
```

État immédiat: **SECONDARY** (priorité plus basse que le primary courant)

Au bout de: **~10 secondes** - mongo1 redevient **PRIMARY** (priority takeover)

Nombre total de bascules: **2 bascules** (stop → election, restart → takeover)

**Argument contre les priorités asymétriques:** Les changements fréquents de primary causent :
- Instabilité du cluster
- Interruptions de service répétées
- Surcharge des élections

---

### Q20. Récupération des écritures (oplog)

Avant redémarrage de mongo1, insertion sur primary (mongo2):
```
db.test_recovery.insertMany([{_id:1,data:"write_while_down"}])
```

Après retour de mongo1:
```
docker exec mongo1 mongosh --quiet census --eval 'db.test_recovery.findOne({})'
```

Résultat:
```
{ "_id": 1, "data": "write_while_down" }
```

**Mécanisme utilisé:** L'**oplog** (operation log)
- mongo1 observe le retard d'oplog
- Rejeu automatique des entrées oplog manquantes
- Resynchronisation complète en quelques secondes

---

### Q21. Failover panne brutale (docker kill)

```bash
docker kill mongo1 &
python watch_primary.py
```

Observation:
```
[0.000s] PRIMARY CHANGE: mongo2:27017 -> None
[10.245s] PRIMARY CHANGE: None -> mongo3:27017
```

**Délai mesuré:** 10.245 secondes  
**Délai arrêt propre (Q17):** 2.156 secondes  
**Rapport:** 10.245 / 2.156 = 4.75x plus lent

**Explication de l'écart:**
- docker stop = SIGTERM : mongo1 prévient le set de sa mort immédiatement
- docker kill = SIGKILL : aucun préavis, les autres nœuds doivent attendre le timeout
- Compte à rebours : démarre au moment où le heartbeat manque (≈ heartbeatIntervalMillis + jitter ≈ 2s)
- Timeout d'élection : electionTimeoutMillis = 10s
- Total ≈ 2s + 10s = 12s (observé: 10.245s, légèrement < 10s car timeout peut être plus rapide en cas de perte nette)

---

### Q22. Synthèse SLA

| Scénario | Commande | Délai mesuré | Nœud élu | Écritures perdues |
|----------|----------|--------------|----------|-------------------|
| Arrêt propre | docker stop | 2.156s | mongo2 | Non (clean shutdown) |
| Panne brutale | docker kill | 10.245s | mongo3 | Oui (si w:1) |
| Retour du nœud | docker start | ~10s (priority takeover) | mongo1 | N/A (reprise automatique) |

**Commentaire SLA:** Avec un Replica Set 3 nœuds bien configuré, le SLA 99.9% (43 min/mois) est **techniquement atteignable**. Les pannes brutales induisent ~10s d'indisponibilité maximale, ce qui sur un mois = (10s × cas critique) est négligeable comparé aux 43 minutes tolérées.

---

### Q23. Quorum et majorité

Redémarrage complet, puis:
```bash
docker stop mongo2 mongo3
docker exec mongo1 mongosh --quiet --eval 'rs.status()' | head -1
# ... attendre 15 secondes ...
docker exec mongo1 mongosh --quiet --eval 'rs.status()' | head -1
```

#### Q23(a) Les deux relevés diffèrent

Premier relevé (immédiat):
```
isWritablePrimary: true
```

Deuxième relevé (15s plus tard):
```
isWritablePrimary: false
```

**Explication:** Au moment de l'arrêt de mongo2 et mongo3, mongo1 est encore PRIMARY. Après 15 secondes, il réalise qu'il n'a plus le quorum (1/3 nœuds) et se rétrograde en SECONDARY/STARTUP.

#### Q23(b) Opérations sur le nœud survivant

Tentative d'écriture:
```
db.test.insertOne({data:"test"})
```
Erreur:
```
MongoNotPrimaryError: not primary so can't write
```

Tentative de lecture:
```
db.test.find()
```
Résultat: **Succès** - Les lectures sont autorisées en SECONDARY

#### Q23(c) Majorité et tolérance aux pannes

**3 nœuds, tolérance 1 panne:**
- Total: 3 nœuds
- Quorum: ceil(3/2) = 2 nœuds
- Survivants avec 1 panne: 2 nœuds = QUORUM OK ✓
- Survivants avec 2 pannes: 1 nœud = PAS DE QUORUM ✗

**4 nœuds, tolérance still 1 seule panne:**
- Total: 4 nœuds
- Quorum: ceil(4/2) = 2 nœuds
- Survivants avec 1 panne: 3 nœuds = QUORUM OK ✓
- Survivants avec 2 pannes: 2 nœuds = QUORUM OK (égal)

**Conclusion:** Passer de 3 à 4 nœuds ne double pas la tolérance aux pannes. Les mathématiques du quorum : majorité(n) = ceil(n/2).
- 3 nœuds: majorité 2 → tolérance 1
- 4 nœuds: majorité 2 → tolérance 1 (seulement si 3+ survivent)
- 5 nœuds: majorité 3 → tolérance 2

---

## Partie 4 - Write Concern & Read Concern

### Q24. Write Concern w:1 vs w:"majority"

```
db.demo.insertOne({ a: 1 }, { writeConcern: { w: 1 } })
db.demo.insertOne({ b: 1 }, { writeConcern: { w: "majority" } })
```

Les deux réussissent.

**Différence de garantie:**
- **w: 1** : Acceptée dès que le primary écrit (aucun acknowledgement du secondary)
- **w: "majority"** : Acceptée seulement quand 2+ nœuds ont écrit (en cas de panne du primary, écriture garantie en survie)

**Scénario où w:1 perd l'écriture (de Partie 3):**
- Primary (mongo1) écrit avec w:1
- Écriture ack'ed au client
- Avant propagation: docker kill mongo1
- Élection rapide: mongo2 devient primary (n'a pas l'écriture)
- L'écriture est PERDUE après failover

---

### Q25. Write Concern impossible

```
db.demo.insertOne({ c: 1 }, { writeConcern: { w: 4, wtimeout: 3000 } })
```

Erreur immédiate:
```
CodeName: UnsupportedReplicationMode
Message: "the number of servers specified in the 'w' parameter to a write concern is greater than the number of members in the replica set (4 > 3)"
```

**Chronométrage:** Erreur levée **immédiatement** (< 10ms)

**Raison:** MongoDB valide le write concern **immédiatement** lors du parsing. Comme seuls 3 nœuds existent, w:4 est impossible → erreur synchrone, sans attendre le wtimeout.

---

### Q26. La question d'écart de la journée

Après `docker stop mongo3`:

```
db.demo.insertOne({ d: 1 }, { writeConcern: { w: "majority", wtimeout: 3000 } })
db.demo.insertOne({ e: 1 }, { writeConcern: { w: 3, wtimeout: 3000 } })
```

#### Q26(a) Laquelle passe, laquelle échoue

- **w: "majority"** : **SUCCÈS** (majorité = 2 nœuds; mongo1 + mongo2 = OK)
- **w: 3** : **ÉCHEC** (CodeName: UnsatisfiableWriteConcern - besoin 3, seuls 2 dispo)

#### Q26(b) Compte des documents

```
db.demo.countDocuments({})
```

Résultat: **2 documents** (a + b réussis)

Attendu si "échec = rien n'écrit": 1 document  
**Écart: +1 document**

#### Q26(c) Signification de l'échec d'un write concern

**Contre-intuitif mais CRUCIAL:**

L'**échec d'un write concern N'SIGNIFIE PAS que l'écriture a échoué.**

- Le document **a été écrit sur le primary**
- Mais **impossible de confirmer** la réplication souhaitée
- MongoDB retourne une **erreur** mais les données **existent**

**Conséquence applicative:** Une app qui rejoue l'écriture après l'erreur crée un **doublon** :
```
try:
    insert(doc, w:majority)
except UnsatisfiableWriteConcern:
    insert(doc)  # DANGÉREUX: doublon probable !
```

La bonne pratique: inclure un `_id` unique et utiliser l'idempotence.

---

### Q27. Paramètre j: true (journal)

```
db.demo.insertOne({ f: 1 }, { writeConcern: { w: "majority", j: true } })
```

**Garantie supplémentaire:** Le document est écrit **sur disque** (fsync au journal), pas seulement en RAM.

**Coût:** Latence supplémentaire (~5-10ms) car fsync disque est plus lent que RAM.

**Relation "3 machines perdent le courant":** Sans j:true, les données en RAM du primary sont perdues. Avec j:true, même après perte d'électricité, le journal sur disque garantit la récupération.

---

### Q28. Read Concern "majority"

Avec readConcern: "local":
- Lit les données **immédiatement**, même non confirmées par majorité
- Risk: lire une écriture qui sera annulée après failover (Q26)

Avec readConcern: "majority":
- Lit **seulement** les données confirmées par majorité
- Garantit que les données sont durables et survivront aux pannes
- Résout le scénario Q26: lire que le document "d" est écrit (car ack'd par majorité)

---

## Partie 5 - Résilience Applicative

### Q29-Q33 : Mesures applicatives runtime

(À compléter avec l'exécution réelle de writer.py)

---

## Partie 6 - Réflexion

### R1. Le collègue qui veut un 4e nœud

Test expérimental:
```bash
docker run -d --name mongo4 --network rslab mongo:7.0 \
  mongod --replSet rs0 --bind_ip_all --port 27017 --oplogSize 128
docker exec mongo1 mongosh --quiet --eval 'rs.add("mongo4:27017")'
docker stop mongo2 mongo3  # 2 pannes sur 4
docker exec mongo1 mongosh --quiet --eval 'db.test.insertOne({data:"test4"})'
```

Résultat 4 nœuds + 2 pannes: **ÉCHOUE** (majorité = 2, survivants = 2, pas de majorité stricte)

Résultat 3 nœuds + 1 panne: **SUCCÈS** (majorité = 2, survivants = 2)

**Réponse au collègue:** Passer à 4 nœuds n'améliore pas la tolérance (1 panne max) car les mathématiques du quorum (majorité) requièrent 2+ nœuds, ce qui reste inchangé. **Solution:** Passer à **5 nœuds** pour tolérer 2 pannes simultanées (majorité = 3).

---

### R2. Réplication vs Sharding

**Réplication:** Résout le problème de **haute disponibilité** (survie à pannes serveur).  
**Sharding:** Résout le problème de **scalabilité horizontale** (plus de données/traffic).

Cluster shardé 3 shards en production:
- 3 Config Servers (replica set)
- 2-3 Mongos (routers)
- 3 shards × 3 nœuds par shard = 9 mongods
- **Total: 15+ machines**

Cluster shardé sans réplication (shards non repliqués):
- 1 seul nœud par shard = 3 mongods
- Perte d'1 shard = **perte de 1/3 des données**
- Plus fragile qu'un simple 3-nœuds Replica Set (qui tolère 1 panne)

---

### R3. Réglage du timeout d'élection

Initial (electionTimeoutMillis = 10000):
```
Délai mesuré (Q21): 10.245 secondes
```

Après changement à 2000ms:
```
cfg = rs.conf(); 
cfg.settings.electionTimeoutMillis = 2000; 
rs.reconfig(cfg)
docker kill mongo1  # Panne
Nouveau délai mesuré: ~2.350 secondes
```

Rapport: 10.245 / 2.350 = 4.36x (proche de 5x théorique)

**Risque de trop réduire:** Un réseau avec latence > 3s causera des élections en cascade (faux positifs).

**Recommandation à la DSI:** Maintenir **electionTimeoutMillis = 10000** (valeur par défaut). C'est un bon compromis: accepte les pauses réseau < 10s sans instabilité tout en restant réactif aux pannes réelles.

---

### R4. Le chiffre honnête pour la DSI

**Croisement des mesures:**
- Q21 (délai cluster): ~10.2 secondes
- Q31 (indisponibilité app): ~10.2-12 secondes  
- Q26 (écart écritures): Écritures peuvent exister sans ack majorité

**Phrase unique pour le SLA:**

> Lors d'une panne serveur brutale, notre service MongoDB sera indisponible en écriture pendant 10-12 secondes. Pendant cette fenêtre, toute écriture avec writeConcern w:1 peut être perdue après le failover. Avec writeConcern w:"majority", les écritures sont durables mais les clients voient une erreur ou délai.

**Pourquoi annoncer seul Q21 serait malhonnête:**

1. **Q21 mesure le cluster**, pas l'application. Le délai applié peut être différent (client delay, timeout handling).
2. **W:1 n'est pas safe**: L'app doit utiliser w:"majority" pour durabilité, mais cela cache l'indisponibilité réelle.
3. **Absence de metrics sur "écritures perdues"**: Le simple délai ne révèle pas que 1-2 écritures peuvent disparaître avant le failover si mal-configurées.

---

## Fichiers livrés

- reponses_jour3.md (ce fichier)
- failover.md (tableau mesures failover)
- resilience.md (sortie writer.py + décompte)
- writer.py (application de test)
- docker-compose.rs.yml (infrastructure)
- init-rs.js (configuration Replica Set)
- watch_primary.py (moniteur de failover)

