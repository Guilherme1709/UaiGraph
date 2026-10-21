import { Component, AfterViewInit, OnDestroy, ElementRef, ViewChild, Input, inject, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Network, DataSet } from 'vis-network/standalone';
import { RagStateService } from '../../../services/rag-state.service';

@Component({
  selector: 'app-graph-panel',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './graph-panel.component.html',
  styleUrl: './graph-panel.component.css'
})
export class GraphPanelComponent implements AfterViewInit, OnDestroy {
  readonly state = inject(RagStateService);

  @ViewChild('networkContainer') networkContainer!: ElementRef<HTMLDivElement>;
  @Input() isMobileView: boolean = false;

  private networkInstance: Network | null = null;
  private isViewInitialized: boolean = false;
  legendOpen: boolean = false;

  private readonly CATEGORY_STYLES: Record<string, any> = {
    Politician: {
      shape: 'dot',
      size: 28,
      borderWidth: 2.5,
      color: { border: '#dc2626', background: '#fee2e2', highlight: { border: '#991b1b', background: '#fca5a5' } },
      font: { color: '#0f172a', face: 'Work Sans', size: 12, strokeWidth: 3, strokeColor: '#ffffff' }
    },
    Party: {
      shape: 'box',
      margin: 8,
      color: { background: '#a855f7', border: '#7e22ce', highlight: { background: '#c084fc', border: '#a855f7' } },
      font: { color: '#ffffff', face: 'Work Sans', size: 12, bold: true }
    },
    Bill: {
      shape: 'diamond',
      size: 15,
      color: { background: '#f59e0b', border: '#d97706', highlight: { background: '#fbbf24', border: '#f59e0b' } },
      font: { color: '#1e293b', face: 'JetBrains Mono', size: 10, strokeWidth: 3, strokeColor: '#ffffff' }
    },
    Institution: {
      shape: 'square',
      size: 16,
      color: { background: '#0ea5e9', border: '#0284c7', highlight: { background: '#38bdf8', border: '#0ea5e9' } },
      font: { color: '#1e293b', face: 'Work Sans', size: 10, strokeWidth: 3, strokeColor: '#ffffff' }
    },
    Entity: {
      shape: 'dot',
      size: 13,
      color: { background: '#757684', border: '#444653', highlight: { background: '#94a3b8', border: '#757684' } },
      font: { color: '#475569', face: 'Work Sans', size: 10, strokeWidth: 2, strokeColor: '#ffffff' }
    }
  };

  constructor() {
    effect(() => {
      const data = this.state.filteredGraphData();
      if (this.isViewInitialized) {
        this.renderGraph(data);
      }
    });
  }

  ngAfterViewInit(): void {
    this.isViewInitialized = true;
    const initialData = this.state.filteredGraphData();
    if (initialData && initialData.nodes && initialData.nodes.length > 0) {
      this.renderGraph(initialData);
    }
  }

  ngOnDestroy(): void {
    if (this.networkInstance) {
      this.networkInstance.destroy();
      this.networkInstance = null;
    }
  }

  public fitAndRedraw(): void {
    setTimeout(() => {
      if (this.networkInstance) {
        this.networkInstance.setSize('100%', '100%');
        this.networkInstance.redraw();
        this.fitGraph();
      } else if (this.state.filteredGraphData()?.nodes?.length > 0) {
        this.renderGraph(this.state.filteredGraphData());
      }
    }, 120);
  }

  private renderGraph(graphData: { nodes: any[]; edges: any[] }): void {
    if (!this.networkContainer?.nativeElement) return;
    if (!graphData.nodes || graphData.nodes.length === 0) {
      if (this.networkInstance) {
        this.networkInstance.destroy();
        this.networkInstance = null;
      }
      return;
    }

    const activeEntities = this.state.detectedEntities();
    const visNodes = graphData.nodes.map((n: any) => {
      const style = this.CATEGORY_STYLES[n.category] || this.CATEGORY_STYLES['Entity'];
      const isTarget = activeEntities && activeEntities.some(e => n.label.toLowerCase().includes(e.toLowerCase()));
      const isPolitician = n.category === 'Politician';
      const hasPhoto = Boolean(n.photo_url && typeof n.photo_url === 'string' && n.photo_url.startsWith('http'));

      return {
        id: n.id,
        label: n.label.length > 25 ? n.label.substring(0, 22) + '...' : n.label,
        title: `${n.label} (${n.category})`,
        category: n.category,
        rawLabel: n.label,
        ementa: n.ementa || null,
        relation: n.relation || null,
        photo_url: n.photo_url || null,
        camara_id: n.camara_id || null,
        color: style.color,
        shape: isPolitician && hasPhoto ? 'circularImage' : (style.shape || 'dot'),
        image: isPolitician && hasPhoto ? n.photo_url : undefined,
        brokenImage: "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64' fill='%2364748b'><circle cx='32' cy='24' r='14'/><path d='M10 58c0-12 10-18 22-18s22 6 22 18z'/></svg>",
        size: isPolitician && hasPhoto ? 34 : (isTarget ? (style.size || 16) * 1.3 : style.size),
        font: {
          ...style.font,
          size: isPolitician ? 13 : (isTarget ? 12 : (style.font?.size || 10)),
          color: isTarget ? '#dc2626' : style.font?.color
        },
        borderWidth: isTarget ? 3 : (isPolitician && hasPhoto ? 2.5 : 1),
        borderWidthSelected: 3
      };
    });

    const showLabels = this.state.showEdgeLabels();
    const visEdges = graphData.edges.map((e: any, idx: number) => ({
      id: `edge-${idx}`,
      from: e.from,
      to: e.to,
      label: showLabels ? e.label : undefined,
      title: `${e.from} → [${e.label}] → ${e.to}`,
      width: 1.5,
      arrows: {
        to: { enabled: true, scaleFactor: 0.75 }
      },
      font: {
        size: 9,
        color: '#475569',
        strokeWidth: 2,
        strokeColor: '#ffffff',
        align: 'middle'
      },
      color: { color: '#94a3b8', highlight: '#dc2626', hover: '#b91c1c' },
      smooth: { type: 'continuous', roundness: 0.15 }
    }));

    const data = {
      nodes: new DataSet(visNodes),
      edges: new DataSet(visEdges)
    };

    const isExpanded = this.state.isExpandedLayout();
    const options = {
      autoResize: true,
      height: '100%',
      width: '100%',
      physics: {
        solver: 'barnesHut',
        barnesHut: {
          gravitationalConstant: isExpanded ? -3500 : -2200,
          centralGravity: 0.35,
          springLength: isExpanded ? 160 : 120,
          springConstant: 0.04,
          damping: 0.65,
          avoidOverlap: 0.8
        },
        maxVelocity: 40,
        minVelocity: 0.75,
        stabilization: {
          iterations: 150,
          updateInterval: 25
        }
      },
      interaction: {
        hover: true,
        zoomView: true,
        dragView: true,
        tooltipDelay: 100,
        hideEdgesOnDrag: false
      }
    };

    setTimeout(() => {
      if (!this.networkContainer?.nativeElement) return;

      if (this.networkInstance) {
        this.networkInstance.destroy();
      }

      this.networkInstance = new Network(this.networkContainer.nativeElement, data as any, options as any);

      this.networkInstance.on('click', (params: any) => {
        if (params.nodes.length > 0) {
          const nodeId = params.nodes[0];
          const node = visNodes.find((n: any) => n.id === nodeId);
          if (node) {
            this.state.selectNodeFromGraph(node, graphData.nodes, graphData.edges);
          }
        }
      });

      this.networkInstance.on('doubleClick', (params: any) => {
        if (params.nodes.length > 0) {
          const nodeId = params.nodes[0];
          const node = visNodes.find((n: any) => n.id === nodeId);
          if (node) {
            this.state.executeQuickSearch(`Quem é ${node.rawLabel} e quais suas conexões políticas?`);
          }
        }
      });

      setTimeout(() => {
        this.networkInstance?.fit({
          animation: { duration: 350, easingFunction: 'easeInOutQuad' } as any
        });
      }, 350);
    }, 50);
  }

  zoomIn(): void {
    if (this.networkInstance) {
      const s = this.networkInstance.getScale();
      this.networkInstance.moveTo({ scale: s * 1.3, animation: { duration: 250, easingFunction: 'easeInOutQuad' } as any });
    }
  }

  zoomOut(): void {
    if (this.networkInstance) {
      const s = this.networkInstance.getScale();
      this.networkInstance.moveTo({ scale: s * 0.7, animation: { duration: 250, easingFunction: 'easeInOutQuad' } as any });
    }
  }

  fitGraph(): void {
    if (this.networkInstance) {
      this.networkInstance.fit({ animation: { duration: 350, easingFunction: 'easeInOutQuad' } as any });
    }
  }

  focusHubs(): void {
    const raw = this.state.rawGraphData();
    if (this.networkInstance && raw.nodes.length > 0) {
      this.networkInstance.focus(raw.nodes[0].id, {
        scale: 1.2,
        animation: { duration: 400, easingFunction: 'easeInOutQuad' } as any
      });
    }
  }

  goToDossier(): void {
    this.state.setMobileTab('dossier');
  }
}
