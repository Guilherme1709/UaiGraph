import { Component, Input, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RagStateService } from '../../../services/rag-state.service';

@Component({
  selector: 'app-dossier-panel',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './dossier-panel.component.html'
})
export class DossierPanelComponent {
  readonly state = inject(RagStateService);

  @Input() isMobileView: boolean = false;

  executeSearch(): void {
    this.state.executeSearch();
  }

  executeQuickSearch(q: string): void {
    this.state.executeQuickSearch(q);
  }

  openBillModal(bill: any): void {
    this.state.openBillModal(bill);
  }

  goToGraph(): void {
    this.state.setMobileTab('graph');
  }
}
