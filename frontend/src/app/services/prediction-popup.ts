import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Zone } from '../models/zone';
import { Estimation } from '../models/estimation';
import { environment } from '../../environments/environment';
import { map } from 'rxjs';




@Injectable({ providedIn: 'root' })
export class TripService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiBaseUrl}/prediction`;

  getZones(): Observable<Zone[]> {
  return this.http
    .get<{ success: boolean; reponse: Zone[] }>(`${this.apiUrl}/zones`)
    .pipe(map(res => res.reponse));
  }

estimer(departId: number, arriveeId: number, dateDepart: string): Observable<Estimation> {
  const [date, heure] = dateDepart.split('T');

  const params = new HttpParams()
    .set('zone_depart', departId)
    .set('zone_arrivee', arriveeId)
    .set('date_depart', date)
    .set('heure_depart', heure.slice(0, 5));

  return this.http
    .get<{ success: boolean; reponse: Estimation }>(this.apiUrl, { params })
    .pipe(map(res => res.reponse));
  }
}