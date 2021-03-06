# This file is part stock_lot_inventory_qty module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from collections import defaultdict
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['Inventory']


class Inventory:
    __metaclass__ = PoolMeta
    __name__ = 'stock.inventory'

    @classmethod
    def update_lines(cls, inventories):
        '''
        Update the inventory lines
        '''
        pool = Pool()
        Line = pool.get('stock.inventory.line')
        Product = pool.get('product.product')

        super(Inventory, cls).update_lines(inventories)

        to_create = []
        for inventory in inventories:
            product2lines = defaultdict(list)
            for line in inventory.lines:
                if (line.product.lot_is_required(inventory.location,
                            inventory.lost_found)
                        or line.product.lot_is_required(inventory.lost_found,
                            inventory.location)
                        or line.lot):
                    product2lines[line.product.id].append(line)

            if not product2lines:
                continue

            # Compute product quantities
            with Transaction().set_context(stock_date_end=inventory.date):
                pbl = Product.products_by_location([inventory.location.id],
                    product_ids=product2lines.keys(),
                    grouping=('product', 'lot'))

            product_qty = defaultdict(dict)
            for (location_id, product_id, lot_id), quantity in pbl.iteritems():
                product_qty[product_id][lot_id] = quantity
            for product_id in product2lines.keys():
                if product_id not in product_qty:
                    product_qty[product_id][None] = 0.0

            for product_id, lines in product2lines.iteritems():
                quantities = product_qty[product_id]
                for line in lines:
                    lot_id = line.lot.id if line.lot else None
                    if lot_id is None and quantities:
                        lot_id = quantities.keys()[0]
                        quantity = quantities.pop(lot_id)
                        # Create inventory lines with remaining lots of qty!=0
                        while len(quantities):
                            lot_id2 = quantities.keys()[0]
                            quantity2 = quantities.pop(lot_id2)
                            if quantity2 == 0:
                                continue
                            if quantity == 0:
                                lot_id, quantity = lot_id2, quantity2
                            else:
                                values = Line.create_values4complete(quantity2)
                                values['lot'] = lot_id2
                                to_create.append(values)
                    elif lot_id in quantities:
                        quantity = quantities.pop(lot_id)
                    else:
                        lot_id = None
                        quantity = 0.0

                    values = line.update_values4complete(quantity)
                    if (values or lot_id != (line.lot.id
                                if line.lot else None)):
                        values['lot'] = lot_id
                        Line.write([line], values)

        if to_create:
            Line.create(to_create)
