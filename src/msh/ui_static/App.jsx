import React, { useState, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import ReactFlow, {
    Background,
    Controls,
    MiniMap,
    Handle,
    Position,
    useNodesState,
    useEdgesState,
    MarkerType
} from 'reactflow';

import {
    Activity,
    Database,
    Server,
    Zap,
    ArrowRight,
    Box,
    Hash,
    LayoutGrid,
    GitCommit,
    Globe,
    HardDrive
} from 'lucide-react';

// --- Design System Constants ---
const COLORS = {
    bg: '#0A0B11',
    cardBg: '#18181B',
    cardBorder: '#27272A',
    primary: '#00E5FF',
    success: '#00FFB3',
    textMain: '#F4F4F5',
    textMuted: '#71717A',
};

// --- Custom Node Component ---
const AssetNode = ({ data }) => {
    const { asset } = data;
    const isHealthy = asset.status === 'healthy';
    const isSmartIngest = asset.ingest && asset.ingest.smart_ingest_active;

    const getIcon = (sourceType) => {
        if (!sourceType) return React.createElement(Database, { size: 14 });
        if (sourceType.includes('api')) return React.createElement(Globe, { size: 14 });
        if (sourceType.includes('file')) return React.createElement(HardDrive, { size: 14 });
        return React.createElement(Database, { size: 14 });
    };

    return React.createElement('div', { className: 'relative group' },
        React.createElement('div', {
            className: `absolute -inset-0.5 rounded-xl opacity-0 group-hover:opacity-75 transition duration-500 blur ${isHealthy ? 'bg-cyan-500/20' : 'bg-red-500/20'}`
        }),
        React.createElement('div', {
            className: 'relative rounded-xl border p-4 min-w-[240px] transition-all duration-200',
            style: {
                backgroundColor: COLORS.cardBg,
                borderColor: isHealthy ? COLORS.cardBorder : '#EF4444',
            }
        },
            React.createElement(Handle, { type: 'target', position: Position.Top, className: '!bg-zinc-600' }),

            React.createElement('div', { className: 'flex items-start justify-between mb-3' },
                React.createElement('div', { className: 'flex items-center gap-3' },
                    React.createElement('div', {
                        className: 'w-2.5 h-2.5 rounded-full shadow-[0_0_8px_rgba(0,255,179,0.4)]',
                        style: { backgroundColor: isHealthy ? COLORS.success : '#EF4444' }
                    }),
                    React.createElement('h3', {
                        className: 'font-bold text-sm tracking-wide',
                        style: { color: COLORS.textMain }
                    }, asset.name)
                ),
                React.createElement('span', {
                    className: 'text-[10px] font-mono px-2 py-1 rounded-full border border-zinc-800 flex items-center gap-1',
                    style: { color: COLORS.textMuted, backgroundColor: '#000' }
                },
                    React.createElement(Hash, { size: 10 }),
                    asset.hash
                )
            ),

            React.createElement('div', { className: 'flex items-center gap-2 text-xs mb-3' },
                React.createElement('div', { className: 'p-1.5 rounded-md bg-zinc-950 border border-zinc-800 text-zinc-400' },
                    getIcon(asset.ingest && asset.ingest.source_type)
                ),
                React.createElement(ArrowRight, { size: 12, className: 'text-zinc-600' }),
                React.createElement('span', { className: 'font-mono text-zinc-500 ml-auto text-[10px] uppercase' },
                    (asset.transform && asset.transform.materialization) || 'table'
                )
            ),

            isSmartIngest && React.createElement('div', { className: 'pt-3 border-t border-zinc-800 flex items-center justify-between' },
                React.createElement('div', {
                    className: 'flex items-center gap-1.5 text-[10px] font-medium px-2 py-0.5 rounded-full border border-green-900/30 bg-green-950/20',
                    style: { color: COLORS.success }
                },
                    React.createElement(Zap, { size: 10, className: 'fill-current' }),
                    'Smart Ingest'
                ),
                React.createElement('span', { className: 'text-[10px] font-mono text-zinc-500' },
                    React.createElement('span', { className: 'font-bold text-white' }, asset.ingest.columns_saved),
                    ' cols saved'
                )
            ),

            React.createElement(Handle, { type: 'source', position: Position.Bottom, className: '!bg-zinc-600' })
        )
    );
};

const nodeTypes = { assetNode: AssetNode };

// --- Layout Logic ---
const getLayoutedElements = (assets) => {
    const nodes = [];
    const edges = [];
    const nodeMap = {};
    const levels = {};

    assets.forEach(asset => {
        nodeMap[asset.name] = asset;
        levels[asset.name] = 0;
    });

    const edgesList = [];

    assets.forEach(asset => {
        if (asset.upstreams) {
            asset.upstreams.forEach(upstream => {
                const sourceName = upstream.replace('source:', '');

                if (!levels[sourceName]) levels[sourceName] = 0;
                edgesList.push({ source: sourceName, target: asset.name });
            });
        }
    });

    for (let i = 0; i < 10; i++) {
        edgesList.forEach(({ source, target }) => {
            const sourceLevel = levels[source] || 0;
            if ((levels[target] || 0) <= sourceLevel) {
                levels[target] = sourceLevel + 1;
            }
        });
    }

    const levelGroups = {};
    Object.entries(levels).forEach(([id, level]) => {
        if (!levelGroups[level]) levelGroups[level] = [];
        levelGroups[level].push(id);
    });

    const X_SPACING = 320;
    const Y_SPACING = 250;

    Object.entries(levelGroups).forEach(([levelStr, ids]) => {
        const level = parseInt(levelStr);
        const y = level * Y_SPACING;
        const totalWidth = ids.length * X_SPACING;
        const startX = -(totalWidth / 2);

        ids.forEach((id, index) => {
            const x = startX + (index * X_SPACING);
            const asset = nodeMap[id];
            const isSource = !asset;

            nodes.push({
                id,
                type: isSource ? 'input' : 'assetNode',
                data: {
                    label: id,
                    asset: asset || { name: id, hash: 'SRC', status: 'healthy', ingest: { source_type: 'database' } }
                },
                position: { x, y },
            });
        });
    });

    edgesList.forEach(({ source, target }) => {
        edges.push({
            id: `${source}-${target}`,
            source,
            target,
            type: 'smoothstep',
            animated: true,
            style: { stroke: COLORS.primary, strokeWidth: 2 },
            markerEnd: {
                type: MarkerType.ArrowClosed,
                color: COLORS.primary,
            },
        });
    });

    return { nodes, edges };
};

// --- Main App ---
const App = () => {
    const [data, setData] = useState(null);
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);

    useEffect(() => {
        fetch('/api/catalog.json')
            .then(res => res.json())
            .then(catalogData => {
                setData(catalogData);
                const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(catalogData.assets);
                setNodes(layoutedNodes);
                setEdges(layoutedEdges);
            })
            .catch(console.error);
    }, []);

    if (!data) {
        return React.createElement('div', {
            className: 'h-screen w-screen bg-[#0A0B11] flex items-center justify-center text-cyan-500 font-mono'
        }, 'LOADING MSH...');
    }

    const totalColumnsSaved = data.assets.reduce((acc, asset) => acc + ((asset.ingest && asset.ingest.columns_saved) || 0), 0);
    const activeAssets = data.assets.filter(a => a.status === 'healthy').length;

    return React.createElement('div', {
        className: 'h-screen w-screen flex flex-col',
        style: { backgroundColor: COLORS.bg }
    },
        React.createElement('header', {
            className: 'border-b border-zinc-900 bg-black/50 backdrop-blur-md h-16 flex items-center justify-between px-6 z-10'
        },
            React.createElement('div', { className: 'flex items-center gap-4' },
                React.createElement('div', { className: 'bg-zinc-900 p-2 rounded-lg border border-zinc-800' },
                    React.createElement(LayoutGrid, { size: 18, style: { color: COLORS.primary } })
                ),
                React.createElement('div', null,
                    React.createElement('h1', { className: 'font-bold text-sm tracking-wide uppercase text-zinc-100' }, data.meta.project_name),
                    React.createElement('div', { className: 'flex items-center gap-2 text-[10px] font-mono text-zinc-500' },
                        React.createElement('span', { className: 'w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse' }),
                        'SYSTEM ONLINE'
                    )
                )
            ),
            React.createElement('div', { className: 'flex items-center gap-8' },
                React.createElement('div', { className: 'flex items-center gap-3' },
                    React.createElement('div', { className: 'p-2 rounded-full bg-green-900/20' },
                        React.createElement(Zap, { size: 16, className: 'text-green-400' })
                    ),
                    React.createElement('div', null,
                        React.createElement('div', { className: 'text-xs text-zinc-500 font-mono uppercase' }, 'Saved'),
                        React.createElement('div', { className: 'text-sm font-bold text-white' }, `${totalColumnsSaved} cols`)
                    )
                ),
                React.createElement('div', { className: 'flex items-center gap-3' },
                    React.createElement('div', { className: 'p-2 rounded-full bg-cyan-900/20' },
                        React.createElement(Activity, { size: 16, style: { color: COLORS.primary } })
                    ),
                    React.createElement('div', null,
                        React.createElement('div', { className: 'text-xs text-zinc-500 font-mono uppercase' }, 'Active'),
                        React.createElement('div', { className: 'text-sm font-bold text-white' }, `${activeAssets} / ${data.assets.length}`)
                    )
                )
            )
        ),
        React.createElement('div', { className: 'flex-1 relative' },
            React.createElement(ReactFlow, {
                nodes,
                edges,
                onNodesChange,
                onEdgesChange,
                nodeTypes,
                fitView: true,
                attributionPosition: 'bottom-right'
            },
                React.createElement(Background, { color: '#27272A', gap: 20, size: 1 }),
                React.createElement(Controls, { className: 'bg-zinc-900 border-zinc-800 fill-zinc-400' }),
                React.createElement(MiniMap, {
                    nodeColor: n => n.type === 'input' ? '#00E5FF' : '#18181B',
                    maskColor: 'rgba(10, 11, 17, 0.8)',
                    className: 'bg-zinc-900 border-zinc-800'
                })
            )
        )
    );
};

const root = createRoot(document.getElementById('root'));
root.render(React.createElement(App));
