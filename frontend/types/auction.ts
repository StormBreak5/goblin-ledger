export interface AuctionItem {
    id: number;
    item: {
        id: number;
        id_mock: string;
    };
    buyout: number;
    quantity: number;
    time_left: string;
}