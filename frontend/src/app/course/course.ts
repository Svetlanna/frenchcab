import { Component, OnInit, PLATFORM_ID, inject, signal } from '@angular/core';
import { CurrencyPipe, DecimalPipe, isPlatformBrowser } from '@angular/common';
import { CourseService } from '../course-service';
import { CourseModel } from './course.model';
import { TripPopupComponent } from './prediction-popup/prediction-popup';

@Component({
  selector: 'app-course',
  imports: [CurrencyPipe, DecimalPipe, TripPopupComponent],
  templateUrl: './course.html',
  styleUrl: './course.scss',
})
export class Course implements OnInit {
  private courseService = inject(CourseService);
  private platformId = inject(PLATFORM_ID);

  courses = signal<CourseModel[]>([]);
  page = signal(1);
  limit = 20;
  chargement = signal(false);
  erreur = signal<string | null>(null);
  pageSuivanteDispo = signal(false);
  courseSelectionnee = signal<CourseModel | null>(null);

  paiements: Record<number, string> = {
    0: 'Flex', 1: 'Carte', 2: 'Espèces', 3: 'Gratuit',
    4: 'Litige', 5: 'Inconnu', 6: 'Annulé',
  };

  ngOnInit(): void {
    // On appelle l'API seulement dans le navigateur (pas pendant le rendu serveur)
    if (isPlatformBrowser(this.platformId)) {
      this.chargerCourses();
    }
  }

  chargerCourses(): void {
    this.chargement.set(true);
    this.erreur.set(null);

    this.courseService.getCourses(this.page(), this.limit).subscribe({
      next: (res) => {
        this.courses.set(res.courses);
        // Si on reçoit moins que "limit", c'est la dernière page
        this.pageSuivanteDispo.set(res.courses.length === this.limit);
        this.chargement.set(false);
      },
      error: (err) => {
        console.error(err);
        this.erreur.set("Impossible de charger les courses (le backend tourne-t-il sur le port 3001 ?)");
        this.chargement.set(false);
      },
    });
  }

  pageSuivante(): void {
    this.page.update((p) => p + 1);
    this.chargerCourses();
  }

  pagePrecedente(): void {
    if (this.page() > 1) {
      this.page.update((p) => p - 1);
      this.chargerCourses();
    }
  }

  ouvrirDetails(course: CourseModel): void {
    this.courseSelectionnee.set(course);
  }

  fermerDetails(): void {
    this.courseSelectionnee.set(null);
  }
}
