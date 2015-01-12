THIS TOOL IS IN DEVELOPMENT - PLEASE DO NOT TRY TO USE IT YET!

[ANTPY](https://github.com/phelixnmc/antpy) offers simmilar functionality
but requires an interactive protocol to build the transactions.

See also https://forum.namecoin.info/viewtopic.php?p=13654#p13654

transactions

Offer to sell a name
--------------------

Seller generates a partial transaction as follows:

Input 0: The previous NAME\_FIRSTUPDATE or NAME\_UPDATE output for the name.
Output 0: Send $OFFERPRICE NMC to Seller's address.

This is then signed by the seller using SIGHASH\_SINGLE|ANYONECANPAY.

A buyer can complete the trasaction by providing inputs supplying at least
$OFFERPRICE NMC and a NAME\_UPDATE output sending the name to themselves.
They can make change for themselves if required, and are responsible for
any needed fees.

Note that it's possible for someone to monitor transactions and try to
double-spend the sell offer by buying it themselves. The seller still
gets paid in this case, and the buyer's funds are not spent.

Offer to buy a name
-------------------

Buyer generates a partial transation as follows:

Input 0: Redeem a previous output for $OFFERPRICE NMC. Must be the exact
         amount in a single output.
Output 0: A NAME\_UPDATE transaction setting the desired data and transfering
          the name to the buyer's address.

The name owner can complete the transaction by redeeming the name's last
NAME\_FIRSTUPDATE or NAME\_UPDATE and sending themselves $OFFERPRICE less any
transaction fees.

There are less possible shenanigans to pull on a buy offer. The main one is
that someone finding buy and sell offers for the same name may complete the
transaction and take any difference in price for themselves (or pay it as the
case may be).

Auctions
--------

A "sealed bid" format appears to be the simplest. A seller of a name would
sign a solicitation for bids using the key that currently owns the name.
Bidders then bid what they are willing to pay in the form of a buy offer
encrypted to the seller's public key. The seller is able to end the auction
at any time and will complete the highest received buy offer.


