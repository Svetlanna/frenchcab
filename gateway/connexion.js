const sqlite3 = require('sqlite3').verbose();
const path = require('path');

// Cible le dossier 'data' puis le fichier 'french.db' depuis l'emplacement de ce fichier
const dbPath = path.resolve(__dirname, 'backend', 'data', 'clean', 'frenchcab.db');

console.log("Chemin de la base de données :", dbPath);

const db = new sqlite3.Database(dbPath, sqlite3.OPEN_READWRITE, (err) => {
  if (err) {
    console.error(" Erreur lors de la connexion à SQLite :", err.message);
  } else {
    console.log(" Connexion réussie à la base SQLite (frenchcab.db) !");
  }
});

module.exports = db;