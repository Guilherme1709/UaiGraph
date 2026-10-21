import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RagStateService } from '../../../services/rag-state.service';
import { PoliticianProfile } from '../../../services/political-rag.service';

@Component({
  selector: 'app-dossier-drawer',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './dossier-drawer.component.html'
})
export class DossierDrawerComponent {
  readonly state = inject(RagStateService);

  trackByName(_: number, p: PoliticianProfile): string {
    return p.name;
  }
}
