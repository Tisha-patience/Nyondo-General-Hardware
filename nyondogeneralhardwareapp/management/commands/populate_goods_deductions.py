from django.core.management.base import BaseCommand
from nyondogeneralhardwareapp.models import GoodsCollection, Deposit, Activity
from decimal import Decimal


class Command(BaseCommand):
    help = 'Populate missing deduction deposits for existing goods collections'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating records',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Get all GoodsCollection records
        all_collections = GoodsCollection.objects.all()
        
        if not all_collections.exists():
            self.stdout.write(self.style.WARNING('No goods collections found'))
            return
        
        created_count = 0
        skipped_count = 0
        
        for collection in all_collections:
            # Check if a deduction deposit already exists for this collection
            deduction_exists = Deposit.objects.filter(
                participant=collection.participant,
                product=collection.stock.product_name,
                payment_method="deduction",
                date_registered__date=collection.date_collected.date()
            ).exists()
            
            if deduction_exists:
                skipped_count += 1
                self.stdout.write(
                    f'SKIP: Deduction already exists for {collection.participant.name} - '
                    f'{collection.stock.product_name} ({collection.quantity} units)'
                )
                continue
            
            # Calculate deduction amount
            total_price = Decimal(str(collection.stock.unit_price)) * collection.quantity
            
            if not dry_run:
                # Create the deduction deposit
                deposition = Deposit.objects.create(
                    participant=collection.participant,
                    product=collection.stock.product_name,
                    amount_paid=-total_price,
                    payment_method="deduction"
                )
                
                # Log activity
                Activity.objects.create(
                    title=f"[RETROACTIVE] Goods collection: {collection.quantity} units of "
                          f"{collection.stock.product_name} for {collection.participant.name} "
                          f"(Balance reduced by UGX {total_price})",
                    color="orange"
                )
                
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Created deduction for {collection.participant.name} - '
                        f'{collection.stock.product_name} ({collection.quantity} units, UGX {total_price})'
                    )
                )
            else:
                created_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'[DRY-RUN] Would create deduction for {collection.participant.name} - '
                        f'{collection.stock.product_name} ({collection.quantity} units, UGX {total_price})'
                    )
                )
        
        # Summary
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS(f'Created: {created_count} deduction records'))
        self.stdout.write(self.style.WARNING(f'Skipped: {skipped_count} (already had deductions)'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING(
                '\n⚠️  This was a DRY-RUN. No records were actually created.\n'
                'Run again without --dry-run to create the deduction records.'
            ))
