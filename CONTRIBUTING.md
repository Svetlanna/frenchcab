# Contexte
Ce fichier vise à définir les rêgle de contribution collaboratives dans le cadre du projet "Frenchcab".

## Rêgles

### Branches
Les branches devront suivrent cet appelation et devront tous être écris en miniscule sans ponctuation:

:nom: (example: malick)

### Commits
Les commits devront être précédés de ces balises et devront tous être écrits en miniscules sans ponctuation :

<feat> <fix> <docs> <devops>

## Dépôt distant

Chaque push sur votre branche distante devra être précédé d'un pull de la branche de développement principale (dev).
Lorsque le projet atteint un niveau satisfaisant sans bugs ni conflit, un merge sur la branche mainest envisageable.
L'intégrateur' est à la charge de s'assurer de la santé de la branche de développement principale (dev) ainsi que la branche main.

## Contributing

**Pas de push** sur la branche ```dev``` : chacun travaille sur sa branche, les fusions sont faites uniquement après validation des tests, par l'intégrateur.

Les commits sont étiquetés en fonction du type de travail qui a été effectué.
Par exemple : 
<doc>Mise à jour de la doc
<fix>Corrrection de la ligne / fichier / fonction
<feat>Ajout de la fonctionnalité

