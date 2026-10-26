
import { Component, inject, signal, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TripService } from '../../services/prediction-popup';
import { Zone } from '../../models/zone';

interface Resultat {
  depart: string;
  arrivee: string;
  dateDepart: Date;
  dateArrivee: Date;
  duree: number;
}

@Component({
  selector: 'app-planifier-trajet',
  standalone: true,
  imports: [FormsModule, DatePipe],
  templateUrl: './planifier-trajet.html',
  styleUrl: './planifier-trajet.scss',
})


export class PlanifierTrajet implements OnInit {
  private tripService = inject(TripService);

  ouvert = signal(false);
  zones = signal<Zone[]>([]);
  resultat = signal<Resultat | null>(null);
  erreur = signal<string | null>(null);
  chargement = signal(false);

  departId: number | null = null;
  arriveeId: number | null = null;
  dateDepart = '';

  ngOnInit(): void {
    this.tripService.getZones().subscribe({
      next: (zones) => {
        this.zones.set(zones);
      },
      error: (err) => {
        console.error('Erreur lors du chargement des zones :', err);
        this.erreur.set('Impossible de charger les zones.');
      },
    });
  }

  ouvrir() {
    this.ouvert.set(true);
    if (this.zones().length === 0) {
      this.tripService.getZones().subscribe({
        next: (z) => this.zones.set(z),
        error: () => this.erreur.set('Impossible de charger les zones'),
      });
    }
  }

  fermer() {
    this.ouvert.set(false);
    this.resultat.set(null);
    this.erreur.set(null);
  }

  valider() {
    if (this.departId === null || this.arriveeId === null || !this.dateDepart) {
      this.erreur.set('Veuillez remplir tous les champs');
      return;
    }

    this.erreur.set(null);
    this.chargement.set(true);

    this.tripService.estimer(this.departId, this.arriveeId, this.dateDepart).subscribe({
      next: (e) => {
        const dateDepart = new Date(`${e.date}T${e.heure_depart}`);
        const dateArrivee = new Date(dateDepart.getTime() + e.duree_predite * 60_000);

        this.resultat.set({
          depart: e.depart,
          arrivee: e.arrivee,
          dateDepart,
          dateArrivee,
          duree: e.duree_predite,
        });
        this.chargement.set(false);
      },
      error: (err) => {
        this.erreur.set(err.error?.message ?? 'Erreur inconnue');
        this.chargement.set(false);
      },
    });
  }
}