#!/bin/bash

# Script de test de résilience avec failover

echo "Démarrage de writer.py en arrière-plan..."
python "c:\Users\PC\Desktop\tp3 jour3\writer.py" "mongodb://localhost:27017,localhost:27018,localhost:27019/?replicaSet=rs0&retryWrites=true" > resilience_output.txt 2>&1 &
WRITER_PID=$!

echo "Writer lancé (PID: $WRITER_PID)"
echo "Attente de 5 secondes avant failover..."
sleep 5

echo "Killing primary mongo1..."
docker kill mongo1

echo "Attente de la fin du writer (max 60 secondes)..."
wait $WRITER_PID

echo "Writer terminé."
cat resilience_output.txt
