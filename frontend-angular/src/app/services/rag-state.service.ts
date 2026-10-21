import { Injectable, inject, signal, computed } from '@angular/core';
import { PoliticalRagService, GraphStats, PoliticianProfile, ChatResponse } from './political-rag.service';
import { marked } from 'marked';

@Injectable({
  providedIn: 'root'
})
export class RagStateService {
  private ragService = inject(PoliticalRagService);

  // Sinais de Estado Reativo
  readonly stats = signal<GraphStats | null>(null);
  readonly isLoading = signal<boolean>(false);
  readonly searchQuery = signal<string>('');
  readonly currentDossier = signal<PoliticianProfile | null>(null);
  readonly hasGraph = signal<boolean>(false);
  readonly currentAnswerHtml = signal<string>('');
  readonly detectedEntities = signal<string[]>([]);
  readonly selectedNode = signal<any>(null);
  readonly evidenceBills = signal<any[]>([]);
  readonly selectedBillModal = signal<any | null>(null);

  // Controle de Abas no Mobile (Dossiê vs Grafo)
  readonly mobileTab = signal<'dossier' | 'graph'>('dossier');

  // Controles de Configuração e Filtro
  readonly currentDepth = signal<number>(1);
  readonly maxNodes = signal<number>(25);
  readonly graphFilterMode = signal<'all' | 'coautoria' | 'partidos'>('all');
  readonly showEdgeLabels = signal<boolean>(true);
  readonly isExpandedLayout = signal<boolean>(false);
  readonly isDrawerOpen = signal<boolean>(false);
  readonly allPoliticians = signal<PoliticianProfile[]>([]);
  readonly popularPoliticians = signal<any[]>([]);
  readonly sampleQuestions = signal<string[]>([]);
  readonly drawerSearch = signal<string>('');
  readonly selectedPartyFilter = signal<string>('ALL');

  // Dados do Grafo para consumo dos componentes
  readonly rawGraphData = signal<{ nodes: any[]; edges: any[] }>({ nodes: [], edges: [] });
  readonly filteredGraphData = signal<{ nodes: any[]; edges: any[] }>({ nodes: [], edges: [] });
  private activeEntitiesList: string[] = [];

  // Filtro computado da lista de parlamentares para a gaveta lateral
  readonly filteredPoliticians = computed(() => {
    const list = this.allPoliticians();
    const query = this.drawerSearch().toLowerCase().trim();
    const party = this.selectedPartyFilter();

    return list.filter(p => {
      const matchName = !query || p.name.toLowerCase().includes(query);
      const matchParty = party === 'ALL' || p.party === party;
      return matchName && matchParty;
    });
  });

  // Lista de partidos únicos para os filtros rápidos
  readonly uniqueParties = computed(() => {
    const list = this.allPoliticians();
    const set = new Set<string>();
    list.forEach(p => {
      if (p.party) set.add(p.party);
    });
    return Array.from(set).sort();
  });

  init(): void {
    this.loadStats();
    this.loadSuggestions();
    this.loadAllPoliticians();
  }

  loadStats(): void {
    this.ragService.getStats().subscribe({
      next: (res) => this.stats.set(res),
      error: (err) => console.warn('Não foi possível obter stats da API:', err)
    });
  }

  loadSuggestions(): void {
    this.ragService.getSuggestions().subscribe({
      next: (res) => {
        if (res.popular_politicians) {
          this.popularPoliticians.set(res.popular_politicians);
        }
        if (res.sample_questions) {
          this.sampleQuestions.set(res.sample_questions);
        }
      },
      error: (err) => console.warn('Não foi possível carregar sugestões:', err)
    });
  }

  loadAllPoliticians(): void {
    this.ragService.getAllPoliticians().subscribe({
      next: (res) => this.allPoliticians.set(res || []),
      error: (err) => console.warn('Não foi possível carregar deputados:', err)
    });
  }

  executeQuickSearch(query: string): void {
    this.setMobileTab('dossier');
    this.searchQuery.set(query);
    this.executeSearch(query, this.currentDepth(), this.maxNodes());
  }

  resetView(): void {
    this.searchQuery.set('');
    this.currentDossier.set(null);
    this.currentAnswerHtml.set('');
    this.detectedEntities.set([]);
    this.selectedNode.set(null);
    this.selectedBillModal.set(null);
    this.evidenceBills.set([]);
    this.hasGraph.set(false);
    this.rawGraphData.set({ nodes: [], edges: [] });
    this.filteredGraphData.set({ nodes: [], edges: [] });
    this.activeEntitiesList = [];
  }

  setDepth(depth: number): void {
    if (this.currentDepth() === depth) return;
    this.currentDepth.set(depth);
    this.refreshGraphOnly();
  }

  setMaxNodes(nodes: number): void {
    if (this.maxNodes() === nodes) return;
    this.maxNodes.set(nodes);
    this.refreshGraphOnly();
  }

  setMobileTab(tab: 'dossier' | 'graph'): void {
    this.mobileTab.set(tab);
  }

  setGraphMode(mode: 'all' | 'coautoria' | 'partidos'): void {
    this.graphFilterMode.set(mode);
    this.applyGraphFilter();
  }

  toggleEdgeLabels(): void {
    this.showEdgeLabels.update(v => !v);
    this.applyGraphFilter();
  }

  toggleGraphDensity(): void {
    this.isExpandedLayout.update(v => !v);
    this.applyGraphFilter();
  }

  toggleDossierDrawer(): void {
    this.isDrawerOpen.update(v => !v);
  }

  selectPoliticianFromDrawer(pol: PoliticianProfile): void {
    this.isDrawerOpen.set(false);
    this.setMobileTab('dossier');
    this.currentDossier.set(pol);
    this.selectedNode.set({
      id: pol.name,
      label: pol.name,
      rawLabel: pol.name,
      category: 'Politician',
      camara_id: pol.camara_id,
      photo_url: pol.photo_url
    });
    this.executeQuickSearch(`Quem é ${pol.name} e quais projetos ele propôs?`);
  }

  executeSearch(query?: string, depth?: number, nodes?: number): void {
    const q = (query ?? this.searchQuery()).trim();
    if (!q) return;

    // Detecção heurística de intenção para mudar o filtro do grafo automaticamente
    const qLower = q.toLowerCase();
    if (qLower.includes('projet') || qLower.includes('propost') || qLower.includes('lei') || qLower.includes('pl')) {
      this.graphFilterMode.set('all');
    } else if (qLower.includes('partido') || qLower.includes('filiad') || qLower.includes('filiaç')) {
      this.graphFilterMode.set('partidos');
    } else if (qLower.includes('coautor') || qLower.includes('junto') || qLower.includes('em comum')) {
      this.graphFilterMode.set('coautoria');
    } else {
      this.graphFilterMode.set('all');
    }

    const d = depth ?? this.currentDepth();
    const m = nodes ?? this.maxNodes();
    this.isLoading.set(true);

    this.ragService.askQuestion(q, d, m).subscribe({
      next: (res: ChatResponse) => {
        this.isLoading.set(false);
        this.detectedEntities.set(res.entities || []);

        if (res.politician) {
          this.currentDossier.set(res.politician);
        } else {
          this.currentDossier.set(null);
        }

        const html = marked.parse(res.answer || '') as string;
        this.currentAnswerHtml.set(html);

        if (res.graph && res.graph.nodes && res.graph.nodes.length > 0) {
          this.rawGraphData.set(res.graph);
          this.activeEntitiesList = res.entities || [];
          this.hasGraph.set(true);

          // Auto-seleciona o nó principal
          const pol = res.politician;
          const targetNode = (pol ? res.graph.nodes.find(n => n.label === pol.name) : null)
            || res.graph.nodes.find(n => n.category === 'Politician')
            || (res.entities ? res.graph.nodes.find(n => res.entities.some(e => n.label.toLowerCase().includes(e.toLowerCase()))) : null)
            || res.graph.nodes[0];

          if (targetNode) {
            const conns = res.graph.edges.filter(e => e.from === targetNode.id || e.to === targetNode.id);
            this.selectedNode.set({
              ...targetNode,
              rawLabel: targetNode.label,
              connectionsCount: conns.length,
              camara_id: targetNode.camara_id || pol?.camara_id
            });
          }

          this.applyGraphFilter();
        } else {
          this.hasGraph.set(false);
          this.rawGraphData.set({ nodes: [], edges: [] });
          this.filteredGraphData.set({ nodes: [], edges: [] });
          this.evidenceBills.set([]);
          if (res.politician) {
            this.selectedNode.set({
              id: res.politician.name,
              label: res.politician.name,
              rawLabel: res.politician.name,
              category: 'Politician',
              camara_id: res.politician.camara_id,
              photo_url: res.politician.photo_url
            });
          }
        }
      },
      error: (err) => {
        this.isLoading.set(false);
        console.error('Erro na requisição para a API:', err);
        alert('Erro ao consultar a API. Verifique se o servidor FastAPI está ativo na porta 8000 com o venv.');
      }
    });
  }

  refreshGraphOnly(): void {
    if (this.activeEntitiesList.length === 0) {
      this.executeSearch(this.searchQuery(), this.currentDepth(), this.maxNodes());
      return;
    }
    this.isLoading.set(true);
    this.ragService.getGraph(this.activeEntitiesList, this.currentDepth(), this.maxNodes()).subscribe({
      next: (graph) => {
        this.isLoading.set(false);
        if (graph && graph.nodes && graph.nodes.length > 0) {
          this.rawGraphData.set(graph);
          this.hasGraph.set(true);
          this.applyGraphFilter();
        }
      },
      error: (err) => {
        this.isLoading.set(false);
        console.error('Erro ao atualizar o grafo:', err);
      }
    });
  }

  applyGraphFilter(): void {
    const raw = this.rawGraphData();
    if (!raw || !raw.nodes || raw.nodes.length === 0) {
      this.filteredGraphData.set({ nodes: [], edges: [] });
      this.evidenceBills.set([]);
      return;
    }

    const mode = this.graphFilterMode();
    let filteredNodes = raw.nodes;

    if (mode === 'coautoria') {
      filteredNodes = raw.nodes.filter(n => n.category === 'Politician' || n.category === 'Bill');
    } else if (mode === 'partidos') {
      filteredNodes = raw.nodes.filter(n => n.category === 'Politician' || n.category === 'Party');
    }

    const bills = filteredNodes
      .filter((n: any) => n.category === 'Bill')
      .map((b: any) => {
        const edge = raw.edges.find((e: any) => e.to === b.id || e.from === b.id);
        return {
          ...b,
          relation: b.relation || edge?.label || 'PROPOS'
        };
      });
    this.evidenceBills.set(bills);

    const allowedNodeIds = new Set(filteredNodes.map((n: any) => n.id));
    const filteredEdges = raw.edges.filter((e: any) => allowedNodeIds.has(e.from) && allowedNodeIds.has(e.to));

    this.filteredGraphData.set({ nodes: filteredNodes, edges: filteredEdges });
  }

  investigateSelectedNode(): void {
    const node = this.selectedNode();
    const pol = this.currentDossier();

    const targetName = node?.rawLabel || pol?.name || (this.detectedEntities().length > 0 ? this.detectedEntities()[0] : null);
    if (!targetName) return;

    let targetCamaraId = node?.camara_id || pol?.camara_id;
    if (!targetCamaraId) {
      const match = this.allPoliticians().find(p => p.name.toLowerCase() === targetName.toLowerCase());
      if (match?.camara_id) {
        targetCamaraId = match.camara_id;
      }
    }

    if (targetCamaraId) {
      window.open(`https://www.camara.leg.br/deputados/${targetCamaraId}`, '_blank');
      return;
    }

    window.open(`https://www.camara.leg.br/busca-geral?termo=${encodeURIComponent(targetName)}`, '_blank');
  }

  openBillModal(bill: any): void {
    let fullBill = { ...bill };
    const raw = this.rawGraphData();
    if (!fullBill.ementa && raw?.nodes) {
      const found = raw.nodes.find(n => n.id === bill.id || n.label === bill.label);
      if (found && found.ementa) {
        fullBill.ementa = found.ementa;
      }
    }
    this.selectedBillModal.set(fullBill);

    if (!fullBill.ementa && (bill.label || bill.id)) {
      const billName = bill.label || bill.id;
      this.ragService.getBill(billName).subscribe({
        next: (res) => {
          if (res && res.ementa) {
            this.selectedBillModal.update(curr => curr ? { ...curr, ementa: res.ementa } : curr);
          }
        },
        error: (err) => console.warn('Não foi possível obter ementa da proposição:', err)
      });
    }
  }

  closeBillModal(): void {
    this.selectedBillModal.set(null);
  }

  askAiAboutBill(billLabel?: string): void {
    if (!billLabel) return;
    this.closeBillModal();
    this.executeQuickSearch(`Quais os detalhes da proposição ${billLabel}?`);
  }

  printDossier(): void {
    window.print();
  }

  selectNodeFromGraph(node: any, rawNodes: any[], rawEdges: any[]): void {
    if (!node) return;
    const conns = rawEdges.filter((e: any) => e.from === node.id || e.to === node.id);
    this.selectedNode.set({
      ...node,
      connectionsCount: conns.length
    });

    if (node.category === 'Politician') {
      this.ragService.getPolitician(node.rawLabel || node.id).subscribe({
        next: (profile) => {
          if (profile) {
            this.currentDossier.set(profile);
          }
        },
        error: (err) => console.warn('Não foi possível carregar dossiê ao clicar no nó:', err)
      });
    } else if (node.category === 'Bill') {
      this.openBillModal(node);
    }
  }
}
