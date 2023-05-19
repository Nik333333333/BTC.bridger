import json
import random
import asyncio
from web3 import AsyncWeb3
from web3.providers.async_rpc import AsyncHTTPProvider

with open('router_abi.json') as f:
    router_abi = json.load(f)
with open('btc_b_abi.json') as f:
    btc_b_abi = json.load(f)


class Chain():
    def __init__(self, rpc_url, bridge_address, btc_b_address, chainId, blockExplorerUrl):
        self.w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
        self.bridge_address = self.w3.to_checksum_address(bridge_address)
        self.bridge_contract = self.w3.eth.contract(address=self.bridge_address, abi=router_abi)
        self.btc_b_address = self.w3.to_checksum_address(btc_b_address)
        self.btc_b_contract = self.w3.eth.contract(address=self.btc_b_address, abi=btc_b_abi)
        self.chain_id = chainId
        self.blockExplorerUrl = blockExplorerUrl


class Polygon(Chain):
    def __init__(self):
        super().__init__(
            'https://polygon-rpc.com',
            '0x2297aEbD383787A160DD0d9F71508148769342E3',
            '0x2297aEbD383787A160DD0d9F71508148769342E3',
            109,
            'https://polygonscan.com'
        )


class Bsc(Chain):
    def __init__(self):
        super().__init__(
            'https://bsc-dataseed2.defibit.io/',
            '0x2297aEbD383787A160DD0d9F71508148769342E3',
            '0x2297aEbD383787A160DD0d9F71508148769342E3',
            102,
            'https://bscscan.com'
        )


class Avalanche(Chain):
    def __init__(self):
        super().__init__(
            'https://avalanche.public-rpc.com',
            '0x2297aebd383787a160dd0d9f71508148769342e3',
            '0x152b9d0FdC40C096757F570A51E494bd4b943E50',
            106,
            'https://snowtrace.io'
        )


class Arbitrum(Chain):
    def __init__(self):
        super().__init__(
            'https://arb1.arbitrum.io/rpc',
            '0x2297aEbD383787A160DD0d9F71508148769342E3',
            '0x2297aEbD383787A160DD0d9F71508148769342E3',
            110,
            'https://arbiscan.io'
        )


class Optimism(Chain):
    def __init__(self):
        super().__init__(
            'https://mainnet.optimism.io',
            '0x2297aEbD383787A160DD0d9F71508148769342E3',
            '0x2297aEbD383787A160DD0d9F71508148769342E3',
            111,
            'https://optimistic.etherscan.io/'
        )


avax = Avalanche()
polygon = Polygon()
bsc = Bsc()
arb = Arbitrum()
opt = Optimism()


async def swap_btc_b(chain_from, chain_to, wallet):
    try:
        account = chain_from.w3.eth.account.from_key(wallet)
        address = account.address
        address_edited = address.rpartition('x')[2]
        nonce = await chain_from.w3.eth.get_transaction_count(address)
        gas_price = await chain_from.w3.eth.gas_price
        btc_b_balance = await check_balance(address, chain_from.btc_b_contract)
        adapterParams = '0x0002000000000000000000000000000000000000000000000000000000000003d0900000000000000000000000000000000000000000000000000000000000000000' + address_edited
        fees = await chain_from.bridge_contract.functions.estimateSendFee(chain_to.chain_id,
                                                                            '0x000000000000000000000000'+address_edited,
                                                                            btc_b_balance,
                                                                            True,
                                                                            adapterParams
                                                                            ).call()
        fee = fees[0]

        allowance = await chain_from.btc_b_contract.functions.allowance(address, chain_from.bridge_address).call()

        if allowance < btc_b_balance:
            max_amount = chain_from.w3.to_wei(2 ** 64 - 1, 'ether')
            approve_txn = await chain_from.btc_b_contract.functions.approve(chain_from.bridge_address,
                                                                           max_amount).build_transaction({
                'from': address,
                'gas': 150000,
                'gasPrice': gas_price,
                'nonce': nonce,
            })
            signed_approve_txn = chain_from.w3.eth.account.sign_transaction(approve_txn, wallet)
            approve_txn_hash = await chain_from.w3.eth.send_raw_transaction(signed_approve_txn.rawTransaction)
            print(
                f"{chain_from.__class__.__name__} | BTC.b APPROVED {chain_from.blockExplorerUrl}/tx/{approve_txn_hash.hex()}")

            await asyncio.sleep(30)


        _from = address
        _chainId = chain_to.chain_id
        _toaddress = '0x000000000000000000000000'+address_edited
        _amount = int(btc_b_balance)
        _minamount = int(btc_b_balance)
        _callparams = [address, "0x0000000000000000000000000000000000000000", adapterParams]

        swap_txn = await chain_from.bridge_contract.functions.sendFrom(
            _from, _chainId, _toaddress, _amount, _minamount, _callparams
        ).build_transaction({
            'from': address,
            'value': fee,
            'gas': 500000,
            'gasPrice': await chain_from.w3.eth.gas_price,
            'nonce': await chain_from.w3.eth.get_transaction_count(address),
        })

        signed_swap_txn = chain_from.w3.eth.account.sign_transaction(swap_txn, wallet)
        swap_txn_hash = await chain_from.w3.eth.send_raw_transaction(signed_swap_txn.rawTransaction)
        return swap_txn_hash

    except Exception as e:
        print(e)


async def check_balance(address, contract):
    balance = await contract.functions.balanceOf(address).call()
    return balance


async def work(wallet):
    account = avax.w3.eth.account.from_key(wallet)
    address = account.address
    chains = [
        #  Create your own personal functions.
        #  Example below:

        #  (from.chain, to.chain, from.chain.token_contract, swap function, 'token', 'From chain', 'To chain'),
        (opt, arb, opt.btc_b_contract, swap_btc_b, "BTC.b", "Optimism", "Arbitrum"),
        (avax, polygon, avax.btc_b_contract, swap_btc_b, "BTC.b", "Avax", "Polygon"),
        (polygon, avax, polygon.btc_b_contract, swap_btc_b, "BTC.b", "Polygon", "Avax")
        ]

    for (from_chain, to_chain, contract, swap_fn, token, from_name, to_name) in chains:

        start_delay = random.randint(10, 60)
        await asyncio.sleep(start_delay)

        balance = await check_balance(address, contract)
        while balance < 30000:

            await asyncio.sleep(60)
            balance = await check_balance(address, contract)
        try:
            txn_hash = await swap_fn(from_chain, to_chain, wallet)
            print(
                f"{from_name} -> {to_name} | {token} | {address} | Transaction: {from_chain.blockExplorerUrl}/tx/{txn_hash.hex()}")
        except Exception as e:
            print(e)

    print(f'Wallet: {address} | DONE')


async def main():
    with open('wallets.txt', 'r') as f:
        WALLETS = [row.strip() for row in f]

    tasks = []
    for wallet in WALLETS:
        tasks.append(asyncio.create_task(work(wallet)))

    for task in tasks:
        await task

    print(f'*** ALL JOB IS DONE ***')


if __name__ == '__main__':
    asyncio.run(main())
