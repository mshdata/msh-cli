const { useState, useEffect, useRef, useMemo } = React;
const { createRoot } = ReactDOM;

const COLORS = {
    bg: '#0A0B11',
    cardBg: '#18181B',
    border: '#27272A',
    primary: '#00E5FF',
    success: '#00FFB3',
    error: '#EF4444',
    text: '#F4F4F5',
    textMuted: '#71717A'
};

// --- Graph Component ---
const Graph = ({ assets, onNodeSelect, selectedNodeId }) => {
    const containerRef = useRef(null);
    const cyRef = useRef(null);

    useEffect(() => {
        if (!containerRef.current || !assets) return;

        // Transform assets to elements
        const elements = [];
        const nodeSet = new Set();

        assets.forEach(asset => {
            nodeSet.add(asset.name);
            elements.push({
                data: {
                    id: asset.name,
                    label: asset.name,
                    status: asset.status,
                    type: 'model',
                    smartIngest: asset.ingest && asset.ingest.smart_ingest_active
                }
            });

            if (asset.upstreams) {
                asset.upstreams.forEach(u => {
                    const sourceName = u.replace('source:', '');
                    // Add source node if not exists
                    if (!nodeSet.has(sourceName)) {
                        nodeSet.add(sourceName);
                        elements.push({
                            data: { id: sourceName, label: sourceName, type: 'source' }
                        });
                    }
                    elements.push({
                        data: { source: sourceName, target: asset.name }
                    });
                });
            }
        });

        const cy = cytoscape({
            container: containerRef.current,
            elements: elements,
            style: [
                {
                    selector: 'node',
                    style: {
                        'background-color': COLORS.cardBg,
                        'label': 'data(label)',
                        'color': COLORS.text,
                        'font-size': '12px',
                        'font-family': 'monospace',
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'width': 'label',
                        'height': '30px',
                        'padding': '10px',
                        'shape': 'round-rectangle',
                        'border-width': 1,
                        'border-color': COLORS.border,
                        'text-wrap': 'wrap'
                    }
                },
                {
                    selector: 'node[type="source"]',
                    style: {
                        'border-color': COLORS.primary,
                        'border-style': 'dashed',
                        'color': COLORS.primary
                    }
                },
                {
                    selector: 'node[status="healthy"]',
                    style: {
                        'border-color': COLORS.success,
                        'border-width': 2
                    }
                },
                {
                    selector: ':selected',
                    style: {
                        'border-color': COLORS.primary,
                        'border-width': 2,
                        'background-color': '#27272A',
                        'shadow-blur': 20,
                        'shadow-color': COLORS.primary,
                        'shadow-opacity': 0.3
                    }
                },
                {
                    selector: 'edge',
                    style: {
                        'width': 2,
                        'line-color': '#3F3F46',
                        'target-arrow-color': '#3F3F46',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'bezier'
                    }
                },
                {
                    selector: 'edge:selected',
                    style: {
                        'line-color': COLORS.primary,
                        'target-arrow-color': COLORS.primary
                    }
                }
            ],
            layout: {
                name: 'dagre',
                rankDir: 'LR',
                spacingFactor: 1.2,
                padding: 50
            }
        });

        cy.on('tap', 'node', (evt) => {
            const node = evt.target;
            onNodeSelect(node.id());
        });

        cy.on('tap', (evt) => {
            if (evt.target === cy) {
                onNodeSelect(null);
            }
        });

        cyRef.current = cy;

        return () => cy.destroy();
    }, [assets]);

    // Handle external selection
    useEffect(() => {
        if (cyRef.current && selectedNodeId) {
            cyRef.current.$(':selected').unselect();
            cyRef.current.$(`#${selectedNodeId}`).select();
        }
    }, [selectedNodeId]);

    return React.createElement('div', {
        id: 'cy',
        ref: containerRef,
        style: { width: '100%', height: '100%' }
    });
};

// --- Details Component ---
const DetailsPanel = ({ node, onClose }) => {
    if (!node) {
        return React.createElement('div', {
            style: {
                padding: '24px',
                color: COLORS.textMuted,
                fontFamily: 'monospace',
                textAlign: 'center',
                marginTop: '100px'
            }
        }, 'Select a node to view details');
    }

    const isHealthy = node.status === 'healthy';
    const isSmartIngest = node.ingest && node.ingest.smart_ingest_active;

    return React.createElement('div', { style: { padding: '24px', height: '100%', overflowY: 'auto' } },
        // Header
        React.createElement('div', { style: { marginBottom: '24px' } },
            React.createElement('div', { style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' } },
                React.createElement('h2', { style: { fontSize: '20px', fontWeight: 'bold', margin: 0 } }, node.name),
                React.createElement('span', {
                    style: {
                        fontSize: '12px',
                        fontFamily: 'monospace',
                        padding: '4px 8px',
                        borderRadius: '4px',
                        background: '#27272A',
                        color: COLORS.textMuted
                    }
                }, `#${node.hash}`)
            ),
            React.createElement('div', { style: { display: 'flex', gap: '8px' } },
                React.createElement('span', {
                    style: {
                        fontSize: '11px',
                        padding: '2px 8px',
                        borderRadius: '12px',
                        background: isHealthy ? 'rgba(0, 255, 179, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                        color: isHealthy ? COLORS.success : COLORS.error,
                        border: `1px solid ${isHealthy ? COLORS.success : COLORS.error}`
                    }
                }, node.status.toUpperCase()),
                isSmartIngest && React.createElement('span', {
                    style: {
                        fontSize: '11px',
                        padding: '2px 8px',
                        borderRadius: '12px',
                        background: 'rgba(0, 229, 255, 0.1)',
                        color: COLORS.primary,
                        border: `1px solid ${COLORS.primary}`
                    }
                }, '⚡ SMART INGEST')
            )
        ),

        // Sections
        React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: '24px' } },

            // Smart Ingest Stats
            isSmartIngest && React.createElement('div', { style: { background: '#18181B', padding: '16px', borderRadius: '8px', border: '1px solid #27272A' } },
                React.createElement('h3', { style: { fontSize: '12px', color: COLORS.textMuted, textTransform: 'uppercase', marginBottom: '12px' } }, 'Smart Ingest Savings'),
                React.createElement('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'end' } },
                    React.createElement('div', null,
                        React.createElement('div', { style: { fontSize: '24px', fontWeight: 'bold', color: COLORS.success } }, node.ingest.columns_saved),
                        React.createElement('div', { style: { fontSize: '12px', color: COLORS.textMuted } }, 'Columns Saved')
                    ),
                    React.createElement('div', { style: { textAlign: 'right' } },
                        React.createElement('div', { style: { fontSize: '14px', color: COLORS.text } }, `${node.ingest.columns_fetched} / ${node.ingest.columns_total}`),
                        React.createElement('div', { style: { fontSize: '12px', color: COLORS.textMuted } }, 'Fetched / Total')
                    )
                )
            ),

            // Columns
            node.columns && node.columns.length > 0 && React.createElement('div', null,
                React.createElement('h3', { style: { fontSize: '12px', color: COLORS.textMuted, textTransform: 'uppercase', marginBottom: '12px', borderBottom: '1px solid #27272A', paddingBottom: '8px' } }, 'Columns'),
                React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: '8px' } },
                    node.columns.map(col =>
                        React.createElement('div', { key: col.name, style: { display: 'flex', justifyContent: 'space-between', fontSize: '13px', fontFamily: 'monospace' } },
                            React.createElement('span', { style: { color: COLORS.text } }, col.name),
                            React.createElement('span', { style: { color: COLORS.textMuted } }, col.type)
                        )
                    )
                )
            ),

            // SQL
            node.sql && node.sql.raw && React.createElement('div', null,
                React.createElement('h3', { style: { fontSize: '12px', color: COLORS.textMuted, textTransform: 'uppercase', marginBottom: '12px', borderBottom: '1px solid #27272A', paddingBottom: '8px' } }, 'SQL'),
                React.createElement('pre', {
                    style: {
                        background: '#18181B',
                        padding: '12px',
                        borderRadius: '8px',
                        overflowX: 'auto',
                        fontSize: '11px',
                        color: '#A1A1AA',
                        border: '1px solid #27272A'
                    }
                }, node.sql.raw)
            )
        )
    );
};

// --- Main App ---
function App() {
    const [data, setData] = useState(null);
    const [selectedNodeId, setSelectedNodeId] = useState(null);

    useEffect(() => {
        fetch('/api/catalog.json')
            .then(res => res.json())
            .then(setData)
            .catch(console.error);
    }, []);

    if (!data) return React.createElement('div', { style: { padding: '20px', color: COLORS.primary } }, 'Loading...');

    const selectedAsset = useMemo(() => {
        if (!selectedNodeId) return null;
        return data.assets.find(a => a.name === selectedNodeId) || { name: selectedNodeId, status: 'external', hash: 'SRC' };
    }, [data, selectedNodeId]);

    return React.createElement('div', { style: { height: '100vh', display: 'flex', flexDirection: 'column' } },
        // Header
        React.createElement('header', {
            style: {
                height: '60px',
                borderBottom: '1px solid #27272A',
                display: 'flex',
                alignItems: 'center',
                padding: '0 24px',
                justifyContent: 'space-between',
                background: '#0A0B11'
            }
        },
            React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: '12px' } },
                React.createElement('span', { style: { fontSize: '20px' } }, '⚡'),
                React.createElement('h1', { style: { fontSize: '14px', fontWeight: 'bold', textTransform: 'uppercase' } }, data.meta.project_name)
            ),
            React.createElement('div', { style: { fontSize: '12px', color: COLORS.textMuted } }, `v${data.meta.version}`)
        ),

        // Content Split
        React.createElement('div', { style: { flex: 1, display: 'flex', overflow: 'hidden' } },
            // Left: Graph
            React.createElement('div', { style: { flex: '1', borderRight: '1px solid #27272A', position: 'relative' } },
                React.createElement(Graph, {
                    assets: data.assets,
                    onNodeSelect: setSelectedNodeId,
                    selectedNodeId: selectedNodeId
                })
            ),

            // Right: Details
            React.createElement('div', { style: { width: '400px', background: '#0A0B11', overflow: 'hidden' } },
                React.createElement(DetailsPanel, { node: selectedAsset })
            )
        )
    );
}

const root = createRoot(document.getElementById('root'));
root.render(React.createElement(App));
