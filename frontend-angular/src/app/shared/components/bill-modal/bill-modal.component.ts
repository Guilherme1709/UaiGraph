import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RagStateService } from '../../../services/rag-state.service';

@Component({
  selector: 'app-bill-modal',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './bill-modal.component.html'
})
export class BillModalComponent {
  readonly state = inject(RagStateService);

  encodeUri(str?: string): string {
    return encodeURIComponent(str || '');
  }
}
