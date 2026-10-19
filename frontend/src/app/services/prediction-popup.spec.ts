import { TestBed } from '@angular/core/testing';

import { PredictionPopup } from './prediction-popup';

describe('PredictionPopup', () => {
  let service: PredictionPopup;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(PredictionPopup);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
