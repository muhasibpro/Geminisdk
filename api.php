<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

$action = $_GET['action'] ?? 'get_products';

$products = [
    [
        'id' => 'j1',
        'name' => 'DIAMOND ECLIPSE RING',
        'category' => 'JEWELRY',
        'price' => 12500,
        'specs' => 'Solitaire Cushion Diamond, Platinum',
        'img' => 'images/diamond_eclipse_ring_1785603522622.jpg'
    ],
    [
        'id' => 'w1',
        'name' => 'ORION CHRONOGRAPH WATCH',
        'category' => 'WATCHES',
        'price' => 12500,
        'specs' => 'Rose Gold Skeleton Dial, Sapphire',
        'img' => 'images/orion_watch_1785603534746.jpg'
    ],
    [
        'id' => 'l1',
        'name' => 'ROYAL ITALIAN HANDBAG',
        'category' => 'LEATHER GOODS',
        'price' => 8900,
        'specs' => 'Calfskin Leather, 24K Gold Clasp',
        'img' => 'images/leather_handbag_1785603570147.jpg'
    ],
    [
        'id' => 'p1',
        'name' => 'AURORA ELIXIR PARFUM',
        'category' => 'PERFUME',
        'price' => 4800,
        'specs' => 'Crystal Decanter, Amber & Oud 100ml',
        'img' => 'images/luxury_perfume_1785603558636.jpg'
    ]
];

if ($action === 'get_products') {
    echo json_encode([
        'status' => 'success',
        'timestamp' => date('Y-m-d H:i:s'),
        'data' => $products
    ]);
    exit;
}

if ($action === 'checkout') {
    $rawInput = file_get_contents('php://input');
    $data = json_decode($rawInput, true);

    echo json_encode([
        'status' => 'success',
        'transaction_id' => 'TX-' . strtoupper(substr(md5(uniqid()), 0, 8)),
        'amount' => $data['total'] ?? 12500,
        'message' => 'Payment processed successfully'
    ]);
    exit;
}

echo json_encode(['status' => 'error', 'message' => 'Invalid action']);
