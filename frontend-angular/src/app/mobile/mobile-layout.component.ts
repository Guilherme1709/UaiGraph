import { Component, ViewChild, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DossierPanelComponent } from '../shared/components/dossier-panel/dossier-panel.component';
import { GraphPanelComponent } from '../shared/components/graph-panel/graph-panel.component';
import { RagStateService } from '../services/rag-state.service';

@Component({
  selector: 'app-mobile-layout',
  standalone: true,
  imports: [CommonModule, DossierPanelComponent, GraphPanelComponent],
  templateUrl: './mobile-layout.component.html',
  styleUrl: './mobile-layout.component.css'
})
export class MobileLayoutComponent {
  readonly state = inject(RagStateService);

  @ViewChild('mobileGraphPanel') mobileGraphPanel?: GraphPanelComponent;

  selectTab(tab: 'dossier' | 'graph'): void {
    this.state.setMobileTab(tab);
    if (tab === 'graph') {
      setTimeout(() => {
        this.mobileGraphPanel?.fitAndRedraw();
      }, 100);
    }
  }
}
