#!/usr/bin/python3 -O
#
# Copyright 2025 Daniel Balparda (balparda@gmail.com)
# GNU General Public License v3 (http://www.gnu.org/licenses/gpl-3.0.txt)
#
"""Pawnalyze base library of util methods and classes."""

from typing import Callable

import chess
import chess.pgn
import chess.polyglot

from baselib import base

__author__ = 'balparda@gmail.com (Daniel Balparda)'
__version__ = (1, 0)


class Zobrist:
  """Chess position 128bit hash, Unique by [BOARD, TURN, CASTLING RIGHTS, EN PASSANT SQUARES].

    See: https://en.wikipedia.org/wiki/Zobrist_hashing
  """

  MakeHasher: Callable[[], Callable[[chess.Board], int]] = lambda: (
      chess.polyglot.ZobristHasher(_PAWNALYZE_ZOBRIST_RANDOM_ARRAY))

  def __init__(self, h: int) -> None:
    """Constructor."""
    self.hash: int = h

  def __str__(self) -> str:
    return f'{self.hash:032x}'


ZobristFromHash: Callable[[str], Zobrist] = lambda h: Zobrist(int(h, 16))

ZobristFromBoard: Callable[[chess.Board], Zobrist] = lambda b: Zobrist(Zobrist.MakeHasher()(b))


####################################################################################################


def ZobristGenerateTable() -> None:
  """Print the (fixed) random array to use in the code below."""
  # generate the 32-bytes long SHA-256
  internal_hash: bytes = base.BytesBinHash(_SEED)
  print()
  print('_PAWNALYZE_ZOBRIST_RANDOM_ARRAY: list[int] = [  # 781+ random integers')
  for _ in range(782 // 2):  # 782 to be even
    a: str = internal_hash.hex()[32:]
    internal_hash = base.BytesBinHash(internal_hash)
    b: str = internal_hash.hex()[32:]
    internal_hash = base.BytesBinHash(internal_hash)
    print(f'    0x{a}, 0x{b},')
  print(']')
  print()


# we redefine a 128bit Zobrist by having 781+ 128bit random numbers
# DO NOT EDIT: editing any value here will BREAK any existing pawnalyze DBs
# DO NOT MANUALLY EDIT: use ZobristGenerateTable() above to generate, if needed
_PAWNALYZE_ZOBRIST_RANDOM_ARRAY: list[int] = [  # 781+ random integers
    0x5b974020de88f98c60a5a1528db4abdb, 0xc8540b981f081962d1dda154ce61cd6e,
    0x936d55ed1da5bcd83b88b9368d36d74d, 0x1bbef2fa66f0daeb7fff75e89e398cab,
    0xeb08bc6ee32e52dbcb6efa064d9fe73d, 0x9a38ffee22375bc56a62e9648ce5d718,
    0x5482247fa1658f30c9a34e4a245bafb5, 0xbe68ef81248e9464a463d58a8a02e861,
    0x6ff76b63475bbd468caa3e42664fa44a, 0x6bec4f34cd44a482e87246994b84e057,
    0xde3a02b0923a2ea7b90c3651e9da18a3, 0x7963c8fb954dd85edcf1620648eda42c,
    0xcf7362a414e10c8012fd0367b95c3fef, 0x140330a329c46eb6005a98b55ac22f54,
    0x4bfbf06a768ed7888a886fd11e713278, 0x5647552c715f2dc8320958209b650795,
    0x15f96965a02348eb4c7a1bfe56dae410, 0x0a1a831e78fa9d9563f3f9fd93cbb964,
    0xfa4ea153b064a88685c067e47a61c177, 0x9fd23bc91b91f866c03eafacda731d0e,
    0x7a9bb9b278fe5c34e858ea8ec8b936ef, 0x4de77524443f04ed70c0f5f41ecb7122,
    0xe3b271d41146ae3d7ae5e7a621d088d3, 0xa5c63ba6964c81299d42507546770d7c,
    0x35a7cb6949c1096c5a04d5154cf3073e, 0x18414be8989c28bdc13431914b366216,
    0x7ac214bb510e72dc7f87bd48c2f2970b, 0x82cf8a6cc6bdcc57c526dddabae1bcd7,
    0x081e0fcddf65be3c6f8fb838c01cd7c2, 0xb8aad51b7c9c6ab2a61c58826b1c4f78,
    0xc0bd3ff584d913553d7dd90e8352096f, 0x43f24a1d01867864f0e0202a3404f44c,
    0x02009844afa67612a0ab632f171c83ec, 0xf63effa1096baf8fde2860c31d55e33b,
    0x1ed88cae3c850d390a517013d1265924, 0x2afa147fb506dc985e87777dc7147031,
    0xd466c2be7a7d1469afca3e1ab95287da, 0x18b4bcfc0d5760a325bde8c59d5aa81d,
    0x4148388277536279b7b540451a9beac9, 0xe6ed0bef74c6bc092cea3bc90b08c30b,
    0x18bb7f101180405ee9311e67f4e81de7, 0x67465df7268829e75663835b2f86d132,
    0x62a319914f80f12b40ae08d32fb24816, 0x2b84f006aeea8ca34745e7a02b14f661,
    0x2ae285f058afcd10747a05a7d6b56dbf, 0x02632256e6e4680d63f4818e8dcbd0b5,
    0x4c275dab2498ceb01505aa8f1e86ce92, 0x7cbb8465a324a86d60667de927527599,
    0x4cc14df734addebeb776588cd8c9f1e0, 0xa69b4f6873c2568e632337b475fab486,
    0xbb8a036a54e928d8cf3c1f0666ca0528, 0xd80e5640d6e343e4d6c698da6e8bca59,
    0xb0d939c7c2ca76d4e20b2a07ef173cc6, 0x344830521b070eb577269d8db4742aaa,
    0x6b53325daf8e810f050f44498db37641, 0xbb399d4219001929d8fbe24321df41ba,
    0x116bb848844d177faa3e917305c61c78, 0x1cb08145b4499a72c96a78d0fe7bce8e,
    0x28ca0d8c0ba0ca431661be41b3c84a97, 0x91253188e0c96670516881fc0bd21406,
    0x3c29efa3c69a31920d619a9b8ae558b4, 0x95ea8706d074c84cfdb83e47b54c8462,
    0x22cc0e649886effbdb4ea117b7069ec6, 0xc1aecd9efc8fb2f10b2c79b08ffe279a,
    0x4cb04de95dfc49d9c2c9f59df1cfb3bd, 0x935cf29a75b1e1f32d4020b20bd50444,
    0xeb62f63e80819d1f951db9746494986f, 0xed74ed9157f2d8f2d22ccdcb10a9363c,
    0xdcc8c3485cf2df56a5acdef157d8de93, 0x0fa8e7cc40dc2a2e34adeb2340f4c718,
    0xec877293fb85530664afce0579406ef0, 0x44d324bbe6cc49edbeb902f15a6474b5,
    0xa4f063e3bf20c914d9201df0a4877f2d, 0x248f17c7b5916ef8ab32d03c867c6cba,
    0x461eba2c99b10127cac982e988cc6063, 0xe3c04baaf8f6d266e7204f04dd95460b,
    0xd8c3152f2e327bb661c1748a8486b046, 0x1fb6c6c21d2662df9811f8b78b6970be,
    0x8d180433b36cd974c2f653586bbb61ef, 0x7767c1cb35a521244eff46024d1d6337,
    0x6ad3e5b032b18de3f530b70fac091565, 0x964c135e8adf6acd745026a86313e821,
    0xe00c4ecd549531bc68c266f3c5a90562, 0xa7c16c74f92edfcd2d7ab14129ece975,
    0x92f922be9c79b52ef8de91a33d3ff639, 0x6b046da34feb1ac122007265d20f2e76,
    0x1bba2f4018f9d3b2ba75ab365449c935, 0x0acdac478640b7373d919ee6ddadb7af,
    0x5da795bdec37b2cc9e14ac597a8d0241, 0x983793518580e06e3fb727545cfe03e1,
    0x83af45646f17e9d18af1de231e360dfe, 0x6a71d0332f7735d4e75afe2af663ace0,
    0x39feb1c54d7e8da97ea552fab05f1e42, 0x9f3849d478fa6888d10f7cf7f04452af,
    0xa9a387a1ab24379c00c176aaac3689df, 0x4ae7f1ab86f5004e3750e131e4602057,
    0xff4ac15cd7160514e0e1ab351bee6d8f, 0xf0ca6e454c8f1d9cd2a932020b6c97ac,
    0xa69c2f05ab907134e4ecc7f6f6079028, 0xbfcc687150e543409935bb00427941ab,
    0x2d4ddb2c83c3680a3efa6b480bfcb53e, 0x56ee2a7a7743d6acf2f2a3170da4e290,
    0x6840d14d2ace39a0d695284db3f276f5, 0xb3715e694e880bbf580100ffd4afbb16,
    0x985eb1d80b3ac389b6673518e265f819, 0xf2b6c276076187ff72ea5cf8002bd2d5,
    0xb3ea233934831f71c5a6742a46d87a85, 0xf9679288d49d13e40f7ff64b0507d615,
    0xb866aa52abaa0a08065b9d806ace526d, 0x7a12d1803210b11c0149ef66df460630,
    0x20b08d24d0833d12441e6a2c391b8e48, 0x6e6385bce2046a30ff1bdfe3475f46e0,
    0x9a3775ac952996da046a612f085e0e8f, 0x738e01eb6e8767640e1bfd88e33f5371,
    0x28433f1cb2531ee329627d00ed9bd7a5, 0xc4c747c45e0f356d026b6db5fecdc7b9,
    0x9fcb500fbb5dbad297a3039f375a043d, 0x86f7693dbec75c2bfc1dba893d60eceb,
    0x956c758667a2e415fb4e294d5b9bacef, 0x59d1f9a285982d475574015287aeff4f,
    0x43e0254b0ca989c53bc446ba7470915b, 0xa527c0910f1f2a93880cc8b63e47d3de,
    0xf85d89e0e3ef6080f9ad002848b7c9ff, 0x53ef5da1b89b8727196bb4445c0fb7f7,
    0x0d933bb8a62f1cd06264c8a99cd49c77, 0xa55e29896cb27557844191b88e01f17f,
    0xb58a97ab3b55de43b301abcaf31e5a96, 0x6da7e4dd87597b1867e21b2e886e3181,
    0xccc8aba2d3ebd79f2014c37cde785fee, 0x0bfff36e63bee867ea3a3bdb33fa4aa5,
    0x9135d22aa7423ea1c546b1c95ac81f46, 0x982615aeaee3a6cb4d6a7fac940eb58b,
    0x5253940ac91021b496f73026de343ab4, 0xd753bb195dbce1996c99ec1d440aa641,
    0x5dfb123e3b8e3a44b7e3ead60247bce8, 0xa2675df36f43a15095523a05e150273c,
    0x4f7b54b0c09d6b9c3e7f77fbe40326e6, 0xc225687879b4f16a5418e3faacd0e8a7,
    0x53b5c78b39f2d83cbfea1ba3b3faad57, 0x2873d8919046b79a6bddd9ea6590287d,
    0x82e350144d3dcfec819f68a341f1fa38, 0x9a9413d849d94cf383a2e3714182e571,
    0x519c8c722d8e4ad40ec73d87cde15b74, 0xd3016e1c58f2018c3b6298a6b7749b04,
    0xfffe9d2f3e2b19e84f11888b4d1e54ee, 0x464781aa07923d9aff6308518cb898bc,
    0xaf9f6c94ff88db285815a6c926fca0f8, 0xb5d0e9bd0e6ba65d75764597d9e0a869,
    0x9f040dda0e8658f6aabfd301d8fa9eed, 0x251395029a39b33080953597d027ebf8,
    0x6031034a21d4ad9a39330e519ad656a7, 0x3b32755f80c97a39f55ae00428a69611,
    0x4aa087fce869464abae6778c74d374d9, 0x8a0da4341c283c50b93a7b5ae45f4f7a,
    0xa6d78b16d9856f3dde983d8f2a91bfe2, 0xaf7bc99763f168c11d19f235b6c4ee3d,
    0x761d8f4ffeb8567c632ea78e97380840, 0x8d3cef2981df4f50385e8eb6f3f5a09c,
    0x20a7faa106d47cd4b58c6e6bd57d4b6a, 0x81a0c0425a63b9d170579679bafb736c,
    0xe5df27d986a7d69a0cae768617387ca9, 0x4faec232729086df371e708776b556de,
    0xd253565f0d18749f38e1d7d88048ca1c, 0xa5cefcde3614dfed6d5340f5a10e7607,
    0x864c84acd387bcd118749cd632420433, 0x1b7fb9485015ec2271a58658eb5e8334,
    0x5531fc79bd449d2463345c93cc84df93, 0xbb85223f1af6f9c469b6e06aa30cf035,
    0x7e2a4e2d986a97aad143b71118798cbb, 0x18fbf17e32546161e9976f3b585f3c0c,
    0x804e17b921111126a36073b1a6b13d30, 0x2d53737f4ff96d0b47fd533cb9495dfa,
    0x943f0b757d1da926d7db3dccc2ac5bee, 0xdb1121f18043e1a8795f612496f50e05,
    0x64227630e8d22d84b3e8bf9157c7f14e, 0xbe9ba968be6af980f6dead31d2dd3d78,
    0x7ac4ab4e165cf2f0cb7170b92d111e7a, 0x48c750487f43c9548acc1726e2b14b20,
    0x8fecd3f9ff249e06d5aa54755caaaf5f, 0x3869605ebca9eef58c8c5ec1148e5440,
    0x2270ed1017fc2a7eb1b678f00887a2a1, 0xbb2fb0df85580565ac89243c11dd7ff2,
    0xfa5960eef972ae85b326ca2a4ccbf962, 0x3980fabd79e0ad476ecb5ebfbce41ccf,
    0x908d92868752bce8b4981fe1aff3d8ae, 0x7047a32d46f86e768346185ac8e20a2a,
    0x55846f667f4d3b374dd35785d21833ee, 0x679dfadad02a32a6a19e070c90b35a5a,
    0xba42a0b2c1f1baae234520cb8c2c6bf1, 0xf688bd7752edbce08cfebafb7e97891d,
    0x72911abaad97e4b42a882ef203552388, 0x245aac1196fd75f0afa8b49f7f67c483,
    0x494732e20312e0963ab66386384dbdbd, 0xcb0a51b19248daef71da59f6d7dc69d0,
    0xb1e394fff8d0132835718ea339c2d668, 0xea84d235d4108fef47de8bf27203f54c,
    0x08faab8789a9edbd34ed3ae552138c30, 0x2713b4f0c93170bf31fd9696a6ed1ff7,
    0x4408b42a58de9f8f79ae7edc0262c344, 0xd65e51d0a54b1eb8061a106d8666ba50,
    0x49a9cb41161d2748fc3ba7c04ad80791, 0xd248a1ccc6048e99bc081d64fd0eb47e,
    0x15ac6cb802977fb2242b6f63b7a392e1, 0x33e45a429cadc55efe1183982aee93ae,
    0xe2bcfd855fb9f12b0c26abb319b22e84, 0x126958cf36079daed932496a76dcd309,
    0x22a916923ad97cd15cb7b10fe95e363b, 0x8ef71f89b9affabf445e93ae1ff9ce8d,
    0x7f695f4266324f9c0342c245498e4999, 0x6a7a3630b24e5d498a26c4ad1c9a0d86,
    0xb23377a8736cb87fea5d454b47ef3a98, 0x75956a84fdc1e4976152e734586d4a66,
    0xd03e7ed13437bc349a5c0a1fe51c9a5c, 0x98959a674b3bc8f8b0f611060710e80e,
    0x0e847f196aac519d5f5f1c97145e0e53, 0x989ef5e025a7298b7e95df2bbf6bbbb5,
    0xe2d1100bc8aafb0b32c166fbb8be8164, 0xe18aa7db96e091cc0e7bc2fe7f4d2b05,
    0x3e8b38f1814f0b7f4aa4565cbf068177, 0x75eabcb374eee62b8a4198aa0d60de45,
    0xb2e08bc3ac0be52c81176c333851135d, 0xf71c7367acfefd8ecd7b18ba09241dcc,
    0xc24f189e518f7afa823c22e5fe5a2de0, 0x86a7d638c4b5a69a124ee405568366d6,
    0xcbef151307597f01f9c8aab7bacb955a, 0x9aae0da0cbdfb66b45c522186e3da449,
    0xe9f61044070ac076931fdcfdca20939f, 0xd5485671203e539b966c8addc1e67173,
    0xb9b468b17783df16f7f9c07179b5d11e, 0x5fd7521c5c48200a7b53f53d1c2f5b0f,
    0x0d4b98b979603c647ceecb13780148f7, 0xb9262502fb5749911aeb698767555ee9,
    0x3c0b6ad697f364547a7bbc96272cb3dd, 0xb1a2e92f70fc720248af2e0d75f27cb6,
    0xdeb3f58adbef07f7e056becfb8aa6808, 0x477d3f0b08b7bc22e953df5a9c94e488,
    0x40de3966e2509b0f67f10cb6e974d56f, 0x19cf42980b3de3fe5c60ca8f8df99b10,
    0x35832ff72d910cdd9e13b5a1aeb08e87, 0xf54cd300fa80d732f28cb62cd7d22c19,
    0xcfffb1f4853e4bee594bd61f085a8d9f, 0x17352e661f1cb5873fff3b4137feec53,
    0x17f1b64eb640117758bea46d44e5241f, 0xcac03c11f2cf10b4489a77c0918a97ed,
    0xf687e9105932342949d1a5abb4e93c38, 0x295922a92aeeda6f254b5408ff46522d,
    0x85cee9dd2b81b8b04ac101e8ed04d204, 0xcf4e5f06a09cb4adae30111674889d4e,
    0x3b45e3da099c6fb14b406bf345949d7b, 0x9a8a6f05aaafaed2912cd1a3a7564556,
    0xd0cb21887a3040ed603f10963fc94234, 0x75f1f8631ea1df4c54b8f19e938dd8c3,
    0x87fd6deeaf60d52eefb9dd6a542c67c1, 0x22d0921e1477848f76cd86d0acefb4ea,
    0x31a181f23a9775f73e57311005a557f2, 0xd2fa1a94ecf2a2904132557f544ad7c7,
    0xd00d4cf4092f70c10e38b259b5f69615, 0x3cb33947b515dc6854108be51749f2b1,
    0x9f08814779161a09997ae66474bc1133, 0x1582a0e157b78a5d7d5e572a7866a847,
    0xaae76cc3f56a12022435ec9d08ae1477, 0x5414184b2a5c06286a6e2f727f3d1a0e,
    0x39756a7ca8230e19d43c02baa7cc417a, 0x385d5730888a2ff8c1b63aaaa5710b57,
    0xb2e0bb23bdebf494498628420021dc5f, 0xd5b8aa6dc0fbf9a59da7d0c40a73b9e2,
    0xb67e58339794408aac7cbb23ca982490, 0x609b7774a29f0eb75726d3902199ae63,
    0x4688c127befdda22fc0e55ca331673f6, 0x427fb692fbcc92f7cd9dd2594927c20c,
    0x4f7c13e595b4d4ad1b6ba3c0c0d19bfc, 0x5570ec6923492d59f0f69c42bd0e2ab3,
    0x79656f86a8b6ce14148b4cb9df966346, 0x3d43f1ed23ce7aa43b6037538565ee2c,
    0xedca2afc4a23c7e43a27b527d9badb15, 0x3f5c02d7dd54be018bd867a434d83159,
    0xb21b31a2a2c0973ad528e71fad47a40d, 0xaaf21cf3d34b0c4b420f7393b768e641,
    0x2c35507baecbc3f7b5c1cf0f7d5520e9, 0x85e4b90c36de324e4c4f295aeb830d8d,
    0x9d5c49542786f8c92270606ee375fe54, 0x6b54fd475bd5b394490f875735a5b347,
    0xda25aa61342ea9e70fdd871e510d518f, 0x6a41f2f1c61d0150c496fe66a38a220c,
    0xa2c9c4fd9339489c88062eea75e26ef3, 0xbbf66e878f89183c3c5497f2f1e2ac74,
    0xcacae9afc0bb4a2a57df0ed725658972, 0xc0e786f707f34ed9c34f5b91fbb00676,
    0x59b031756af617854955d318e2c0c516, 0xb5183ebdb79ccdc62c3560bbc68971b6,
    0x563d3bdc6ee4e95c875dfe8a7eabb994, 0xa145e97a600733a424b2f709c1f22ffb,
    0x49cd23e014f3a3ccc81362bea0e7c226, 0x0308672ae6bb54b949476e66fdda46df,
    0xd9eeb968833ca52ef67f3b50b98cc110, 0xb716fdc439f7cf6ec39428376baee75e,
    0x6f29a20803fd2c55cb65739dca389bef, 0x32354c7f0e041f89764374e100782f35,
    0xd22a1a72f0db66873a32b4dd3012213d, 0x8e5aad65d679936847e72e327ce10ef8,
    0xdb5562cb8209bbdb10da2fdfefbf63e2, 0x3c6283eb3baa32f6c1afe1bdfdabca84,
    0xc224be5f08d63def50a8587099ba369c, 0xf3c8012c7b4e14dbd4f40570d9d8fa33,
    0x1831f96611d8dc91959bc3acff699fda, 0xcb294158388124e6bbdf1888360db92a,
    0x0ce5f8def32ffa94d8be090b1bf2a29e, 0x5c3f55d57d543d5e242976d4bac9d6c1,
    0xd5391bed31f43cec7d35cb3ce225585d, 0x0c90edaed0d2829fc40ad1d7f32c0aa6,
    0xdc59115e28c5a3cd1320595e71a00d03, 0x36e2a55dd22ec08d0d1aa1c46d1bf013,
    0x2f759c22a8b3fd7d9987d383822a8080, 0xd4df8b475a839a6791af33a1dba134b1,
    0xdbdba931e23676efd31dcbc2276f561f, 0xeaff790cabb66b8ae148eca2400d81de,
    0xe05314d09c6b7c72438b76900a6ba5b3, 0x5966692aa30ccf2576f7e23af4bc67af,
    0x48ef323b3f40dde11e7330735da0fc89, 0x71b6c0c4dc1a7cde6e22f7f25f7ebbdd,
    0x3fa651e81a763b9aadb22499b9c147b5, 0xf99bd2dbd2de9fd6f3e51ce5e0378e80,
    0xcd4d37ab82ecfab48099c904f8364236, 0x764707297d6f56a4b6565823cca711cd,
    0x4facd10f3ec2924e86e077e3adcd80a8, 0x6f63182352e9184db98c9d90540c8b20,
    0xcd6cf9dcfa174205e2dcd479387dfdc5, 0xf22998dd31321be6e405b4424fbb256e,
    0x5240cfed9e789a58ff93b5af96e49224, 0x66d054419ae6e43e04dc0a6ff5c1104b,
    0xd4bf8f16a2ab11784763f7ff0e5f914c, 0xa06ade09d07d1fb042b00cdf27103318,
    0x3f779085379f9377adcdb67d617871b2, 0x8d7c109717ede08d9035b8a58c3bd000,
    0x321d6de55670305fe936d7d493ae519c, 0xa317462811de23b1e58ec7407197a16d,
    0xbbf091a22e9b6d16f70fa253d6f0d5f9, 0x0a44c70fd356212d4a1d0cd5e45e955b,
    0xb577c5aaca99088f3ed61634f1f55dcf, 0x7b55ba352cf940d2281f0b13f81e6234,
    0xe87477eb633f4a23145fae8f6a8a5dd3, 0x8dcbb55abc8e151322170e632ffd2b4a,
    0x10353010126734687412cd4ec9b61767, 0xbc0fd3a757910f8faed74399b8857bfa,
    0x6e4dfb0110378da542ce5d80f0751a08, 0x78e38f9151f28f767181db802dac8095,
    0x7573fbea0a2f854452af7c09fd73e0bf, 0xe46412edf7fa5f09656287b0f4f9553b,
    0xf21ca27f13db3fa596f849da7d8312fa, 0x5bc9a6f6660e427478d4de5e792b6a81,
    0x4d01ab4795e8dcf7d76f16b04368afa2, 0x12fcffe40cd25826d6fa8ba8865b9c5f,
    0x8a22584990ded8b9acf33612109ee68a, 0x3074c72731aba7085ff1a422f01fa481,
    0x28366739f5a2a082ca305152b0303929, 0xbe9146eda494c6bbe36d1fcc8b6d226d,
    0xef42173de2fd830f210507511e531e91, 0x8932f842c3f4bad4ba75994b8ef9da96,
    0x325e3920c5d352a48fee22fe7476f487, 0x02dfd3366c4274891bb6da5556d1fa01,
    0x46fc62ab2d0c42d7c84ee38bb4941335, 0x79d6fbe73e0a48b77df858aae0f6fcde,
    0x04583ef78f184d289105bc6ce1358876, 0xcb932a73e7eb8404e0bfb048468838a2,
    0x399208a4c6fa75f65d58f2a7634e2ccb, 0x83f3f353a7bb60cf19355ebae9c02df2,
    0xf157583c543942ceef343b360e66322a, 0x3770be607bebda5cbd08540f9fee59a3,
    0x981a91f1d4dc475a2df4d07a83a1a2a5, 0xf00681f073fa74693c99cc9a5cef5b6e,
    0x64f9cc9415a6b7265df6d73f52e30d78, 0x908283d0f8c18d926caa3ef5bc3784b8,
    0x858339c1af61b37ab362ad10001e5edd, 0xd882eed42549d01f205284d45f6b27f3,
    0x19ec61ad3c131a59d01036be5e8b4066, 0xffbedaa56aa9d0872338e8b28ae80c3c,
    0x384d63379913ea406f9eb2e0706fe7da, 0xbab6af61aef070c57367547d9aaf8a6f,
    0xc78d607a9b736e52b079644b9f2c817c, 0xbb09d94f8077b3185f30257a700df4f9,
    0xe625432458d60a17f701dccc9f73460e, 0x081e1790312949f446059013ad0aa93f,
    0xca69a35ed5ec1e0fb583225aa224ea34, 0x17306027237e440c1d8b96ab1252f3b4,
    0xd9cf72c7a34f68d57bcacb34dc2110ec, 0xb0f6eaddc13969456970aead1ceb228b,
    0x8897880cbb1515fdfd3c04068aa73423, 0x7d731b95d749c921e22b4f00f3fcf8b5,
    0x4398cd921f5f6a253a8396371e0d140f, 0x15e4ce59306fe21c960251c85b556736,
    0xeec85191da823d9b5880d35a7489d2a3, 0xc854f5214dd16320e0bf271e8d8205c3,
    0x6372a63b40757ba49eab4ec57f6c58c4, 0x9e161c43a002bc7e8b3e57ba33ec83e2,
    0x93bddd0328a3b1105e05cf354ffed27e, 0x8305f16114b7ab6a03fd4053947cadc7,
    0xe1823ba22c55b87d1f109aa32378dd2e, 0x7a3af6df663e962b40ae8d9794e5fed7,
    0x7ce9c8c4591b55fb5e0eae66dde4576e, 0x1522ca3254fe3aa8c2478150e7db0cc5,
    0xd388285f986f8ae48a7b8508cc4c03e2, 0xea9047f6574a274d8c27fb59a59daf6e,
    0x5664a65877ad5c29672b14e5ec9beba3, 0x6687c5a3a7d7bf9b36191e1e3699be1f,
    0x707a84a04a79b0d5abacb1049f4bdbea, 0x11a76e618a20072eaad6a91f79eebf75,
    0xc5c126f6f484f0abd638525d37393c5c, 0x964cc3732866887d4583cc9167cff90a,
    0x5d40f430d37c7214439092a8a5c1d86f, 0x5efc4a027cbef55b58d4984874fb7d84,
    0xdb92549c816a93019d2c7944f5db0455, 0x44b7a0ca579b8aed161e517c358dc2ef,
    0x0cd582a78b0217f5b35eeab64bc9b583, 0x9062341029940b9bea7e82d9c1a5aadd,
    0xa8f164a80bf689d8938458df509b6e8c, 0xf0cd654cc4175a05b7208d15eba4aaee,
    0x354ecee69920e1752c1d08a10f480a9a, 0x7510b097d792ce9e9bd83f53d82f0b0d,
    0x0e0bfd7fdd8cc7e4cbbc76a4c491187b, 0x685ff913712598a90259c943888708de,
    0x817580c4f719544656c78b581fb8fad4, 0x41c2019a6d891593089fb2ec30859380,
    0x9cae55981fba4432575815678c2fef95, 0x80f97a541165e9ed54658c4e9e1be811,
    0x5d458c820f3e7264dc98c6d1580fc7b7, 0x438af5c8b0438a417d22f2dc9bb8cae0,
    0x4e1e6ad1ddb93bef61281e17996faaaf, 0x7625b653a2152c0271b804d2e3bce05a,
    0x0a525179f178de55e6fe4b0c1f77de87, 0x198c2c4106b5bdfef0385868f35f661b,
    0x1cdf7751eb6931bbc1b3f94e470fea99, 0x32382120331565709700c3f9e36d3630,
    0x237df49a67497ed6190ee9ad5d2fc88a, 0xf24aad36b38fdfc0474a0a6ef0b1a173,
    0xc87b9009979f685953f4c38015eb96d9, 0xa2ce04a5f5347aefcd58575cf8dc7296,
    0x43c6ab553c919bfafab9a33d5a7ca9dd, 0x0d7f6f606d2e4832706f87e9967b6b47,
    0x90a4dc979db90ba1df7df71b6ef25834, 0xc28ecb24501628d5464fb8f7cd44b389,
    0xf03174d4edfd62bc95c2478ba1ddd58a, 0x9de9bfae46a0070a7d2af198136ef8dc,
    0x1ac14a5698ee412ba28f42fb9234165f, 0xa7e6c4043ac2f33ced8c2a4a5fa5f24f,
    0xb3a044e049b92c18c1158a594ce2d4fe, 0x5776bd26acb85bd081ba2c3c60e8d90f,
    0x148cbb31ba85e52ac9458ab8edf5c277, 0x0b6a2192cfd075345402d090f6072170,
    0xf32846e622ba143b169afb9222205295, 0x2b0adb7f620003791d854f31df69ce6b,
    0x87f8c254bb9420e12032f939493cf015, 0x169a1ce5b0395c68a9614d3ed1be66e2,
    0x0608f43c546909e6061ce21cf875ad5b, 0x31468a6242d7effbd8fc770192b4175b,
    0xf2f791b830a3b941389ff93a5973328f, 0x2230173777580a869e2da72fff57636f,
    0xbfafad6e4d8fc6a303d2d348724235bf, 0x596f248d30578dcdaa741dc8c7e4c2ca,
    0x42ef82d4567f86d4685648d750706fa1, 0xc6b249be1e7f4aec5a0cdffb532afbec,
    0x18e3724a370031d1f8d3a17293e48f04, 0xc0228e96f3807cf0aa723fd4703c5976,
    0x0a602ddb23062f80ed7ad82eb113e976, 0x387a036ea1f56e833d28b636f03e53a9,
    0x54fd4d02da245415e91a0ad3bd2576a0, 0x922823b76d9a44e64ea0412027cf4747,
    0x54861fe3f0a96ae266dca5fa0d433c8b, 0xd98f00bfe0eaffffd35ab54f0b2f4768,
    0x3a53a5de41d616c1d818d63a5c663457, 0x58feb48742785a1850aec7119a143ca2,
    0x71c5ac52eebe856bf26058989cf7519d, 0x197b7fa0407329522f2b61c12f7ae919,
    0x2402c9e44dc03ba0a3dc4fe4226804ec, 0xd0d618bef317555c723e572cadc07608,
    0x8e87d7572ae899ca7970a10545e682d1, 0x7c3c1d4575d44bf9943ae00c9d2114e0,
    0xb3d8a133557e8ec610c0a33a43bc705c, 0xa9a1f08c380f84fc45dfd6b2d1cb77a0,
    0xfda50cc8c792f1fa2966941f61e13165, 0x15ee32f574264d7debd4cbbab76643dc,
    0x81d14e385c5da0c04c80fab8acd60440, 0xcd39a2daf94251c7354483e8389ebdd0,
    0x3cc3e1a976e1ff59e13322226cb03127, 0xc8bfdc718d89e85e83633bf30e729bec,
    0xf092b329e2141590cd4f85c8c78ee5c1, 0xfb2bc2fc16352fa8cd3965616ae97eb8,
    0x4bcec8ad89c35d9a64efac1b94fa197a, 0x27fe98ee8de97d0abaf7c7e7eae214af,
    0xb74e9950926de9a731cd0804f9b16376, 0xfc42c77b03ab475abc30f01b4d86242a,
    0x114490d76bb486b0f19bdbd23320f622, 0x4e5882bff36e2027f877ef4e4e01733a,
    0xa35bbdda94630ac1da2dadf8e447b545, 0x1354f1871da3ac001606d931fed73fa3,
    0xb759d410137379c057f12fa93ddfa6c1, 0x607580a138da4e31dabd4453f4a9fe73,
    0x5faaabffea576426615b51de9e117079, 0xc07c72590b690dbcb9e12c33206227ac,
    0x1e408f38da5895e949b37548858fad85, 0x2bd0520ca17a99c92ae087cf83d7ebba,
    0xc316cf4ec9cff5affb5d0d43f655c11b, 0xae049c98cbc63f1ff76d2e0d50a61a31,
    0x0a63a92e90236122fb85f625f8bf4412, 0x7d8ba53c7bb6341557e694297c099f2e,
    0x378830579abf336e80c2dbb4b525b23a, 0xb0acb45a8221eb0212e48d45cb18f2c2,
    0x16b5d1c471d1ddfd399ee0f5dd892ef5, 0x00e1c7e7fb0d5639340efebfb553f4e7,
    0xdb6cc214498a75e72a511d464e2a4594, 0x37c927e1099ced5c61301b2071d948f4,
    0x436b6261941b2fbf3cc73bc602e40197, 0x14282ee3177b11233b780b6341e74289,
    0xec88b3576177ac539d5d3b7426729644, 0xc2a0fbfae3359bd2cced0f33abf29c1e,
    0x2ff871856c047d76d70f899e6c049d17, 0xef9a8bb15d7eb59502b62084fae7119b,
    0x9fbc024fa9607ffea49d9904673166ce, 0x2cfea68cc3fe697373ad380bca528e89,
    0xcdb85ad03f5f73b0bd67bd99e82d0bb9, 0x8b9a28ddbd977339b12e49c157541ded,
    0x0418ab539ffd7e1b011ff5e0ef5dd058, 0xc12a7254bdc9b4629b3bf3f8423a1a07,
    0x076d0e4ae81c49c59468de4a0fb12c91, 0x277b6f4620442994e3fb66473816e2ed,
    0x6208e574e217fdc61da8d144d2589691, 0x55f48077f9cb80d9278ce63436c6b1f0,
    0xaf62d1d0d8fc3c4340be159019d17e3e, 0x115eda66e33831b269f568dea4df7a61,
    0x6f3977157cdf60bebf22af33f984b9bd, 0x97a6ed3c44c5faba3846d9f1e7b79435,
    0xd19b01f1e0c7c31e1788eae1e3e2de6b, 0xe8efa562159af34e2d19457c14a3874e,
    0xaed31ad627f62e6f247decc6185c64ad, 0x32a2231de92098eb614ee77bdd711d4a,
    0x785c26181c5cf89c2fba179a7a6fd8eb, 0x2c0761857863fc6ae3e178a590d3cb34,
    0x104b4dfb1b68becf119f0e195403c970, 0x1768f3ca655350faed452f7280b688ef,
    0x83bf8286b1918fdbaec0bd58b196ad15, 0x49c751c8bd1000793932f0d64a14440f,
    0x4b3a033b0db862d35aee0bb827db6997, 0x8d1b38ae52fd5d886888aaa0f020a4bd,
    0xd5e3b93e7756eef49c92a5ade3a85f5b, 0xb5240fb586edb843b5f19152412fdf6f,
    0x8381824ea64e4f81812b07216081ddd0, 0xc706976a0e76b490342a7f98b08fdd32,
    0x8a3b8629cdd4ce77bb70028c5ce4474f, 0x2e64713333bdec7e4b3c2faa7a7aace5,
    0xe0a61066580340b0d46fe128f948a77c, 0x3879ac270c673fee85f0eee6f693c868,
    0x4567b195e77ba871083edb9cda26e047, 0x7af96014d2ddcf81a28fa60b5feb6bec,
    0xa09d43f9aadaf5ef83bed3d9066debb0, 0x6bbd54839377cd26d2b36cd571e5c11a,
    0x715c848a2bd9b3c1400309c93682a222, 0xdd9fecc7a6a46c1a2c6fd94b91b1cba6,
    0x5a465b14017522ca04495ab8b958bddb, 0x42b7c18a1600a340b8d0532cd7128a15,
    0x484769af9154173c2444f75ba2be108e, 0x5263c78f38f16643a094a520da19f356,
    0xf3e2596bcec5aa5fabe1521da8f10ccc, 0xe8ab9132268b9962e63d202bacb71143,
    0x1ba3e1d4c72f31925539dae5c5661107, 0x852a6c7bf890e1058ff605cda8676f47,
    0x8a75a0443a4cc875d5b0b914967be3fc, 0x11f9d1464d52bf6907ceb22ba5ba0a26,
    0x851ff8ed62230e63280074f63ed6a647, 0x4eb10faf6cc8b17a5b03f9b1f98711bb,
    0x6260d2f793286b26c80eafe58927b689, 0xbaadb2d4d64763919bf8b7225610da94,
    0x641e1d295086478862f7861b6ddbb8fe, 0xdf95fbf5a05cd69c4ead5ec66b0a7b98,
    0x99e5c0d94c45931eb4abc479c51f97e9, 0xb9b435234e475ff10e39f75c4eba5d9f,
    0x1be9658723601473a987a76a8160cfef, 0x6e80d7fbd2095088dca200221fef03fe,
    0x8362750015c5bc5006f42c203e62b7d4, 0xc050f16d22a879da84f840a44a16eae0,
    0x58c9f8299615af1ca113d051a63ce08c, 0x7a42a955418a5ad52ca16447110f5eb3,
    0xe22b048c1396dd5c176cb8a16d6eac41, 0x80e4f2d9f43e05b38b3a91833f7594ae,
    0xabe13228ec6c9452f90ba245f8c73696, 0xfb43239a4e40015d9fa18f16b7e0aaa4,
    0x9b069d210bab5bd88db6b89d7fd65298, 0x8f80c902305dfe24aeac7b8a96f6e13e,
    0xc46f476a4b9fd65322b6211fc9bd3a16, 0xc3ccff8896ece580a8d8c373ae0983d8,
    0x413a863dc999f719797623c710d3a560, 0x4f083aafb038e6cfe972deeba2c8f1a4,
    0x0acbd3d8a0c6155849ce938637e002a2, 0x3154caf8dd08e1330d0597128d5ab6ae,
    0x87a95c3173d7bb1dc4a743a00d67860f, 0x37ed9900b973c8c86bc4f8bfa84a436a,
    0x466640a85bd0093928f5486aad2cb578, 0xbafe3f16da2fa5870f50a54a0c8ca768,
    0x718d3a27ac8009cb2a388bf0ee03a39b, 0x14bb7e382d8ca182567314e8385eedd9,
    0x93d2a5484142a19643adc6a36252e10f, 0xfdf2d7864261415b4b5eb1ad76238b05,
    0x36af73a1db52fb2ef6f9f9db1197d431, 0x75d5c42f5f2ce315291e99d3015bd5b1,
    0x7fe033dc870ad3970775885e269ed060, 0x8bd4ac0a91f44245c7e7bd161b4ccfbe,
    0x38d9421ccdb3e68fb7c52c78d154a2c8, 0xbfcc3bfc17243873de53d10edad81633,
    0x8466401143d709371f3e5fbba2487537, 0x152a5933fe8bbe8ffd6e15d7738b16b9,
    0x8daafa969e4a6baf8592ee1ff10963d1, 0xafdc04a90c04ce4a535c93c6e3ad10cd,
    0x26a4c90a184e938287c0805b3ab97d3c, 0x212af3032cac1287651f41262e403459,
    0x3b358dd1da18c419b77ed4335b7b481d, 0x94f1a6a678a8414d502a80d7206de75b,
    0xac0debb0091bc82c3cdd9e4a8a83265a, 0xfe11499836e20d7aec1f93df891037e3,
    0x816e72c9a9691b9bebe854d0fae054f7, 0x1c5de6b78f9214b7109335ecc1badf2c,
    0x464fc8db3d8e6777c2edb49953bbaea1, 0x11d8c629c438ad55cfa6ce71e48b402f,
    0x71220f1750e55637aa52c6c6488f600b, 0xd3b39f50dbf298a1ac34ffb5cb6865f9,
    0xbd4ffefc0686e7093bcab1d1ecafb86e, 0xd8ca104d42d7c17e10a9a3067005cbe0,
    0xc901af4976642ea6a295d9c4004b6871, 0x1454c2a763f268cc7bf2817298467168,
    0xe4698d4b7ea1dab0104c9302cf2468fd, 0x07c684ec49a6bc74843aec69d75010f1,
    0x74473a9cad40b3c12d07843659e2631d, 0x16081674d0570a9c0abcb04cf1e3e179,
    0x8fc3902b2d9e7efc51c5c4f9b7107d64, 0xa205c43a1101338431dfad9ad0c1b0da,
    0x87754d2c47e39c4244fb3bb42a747be1, 0xf86923db68bfd279d4b1ba22e4e2efb6,
    0x015cd4c9c429bd28f25d3279c71f6e25, 0x053c666e9cb6dcd2c9d65517723142e1,
    0x18c5b3659a38619e1843c68f3ad96de2, 0x89c7c34925cfd2581faabe13c2e0cf88,
    0xa775ba8342054795ab36d139a56d1ed0, 0x83ab2ba9eab9a537861ee8596f1e56b6,
    0x04815352d1c021a81e97ca54599afe2e, 0x38d1eaf969a2e033262f73043e5ef215,
    0xf7a833acdfe031cb7047c603e62ea075, 0x2f1950310acdcf81706635c656bc3ff5,
    0x92f6060b2b77b5cdf1d7cd5cb6fc49ca, 0xd98cd4ca6ae69204f3b328b94c6cab03,
    0x57748d5f7114c35467542df507c55469, 0xf8506fe902e3612e45786c15683d2b94,
    0xfd94e908591e4eac4ff59bededd89349, 0xee3a4d40fe9b49a07b16fc6b07270633,
    0xbebed3f2f93a0e1b600eb5497a32d4d9, 0x403e1a7fd315cba4229026f5ef1e7901,
    0xb2ca8618925bb74376d5ec92b0fd488f, 0xefc6c2fdf7d737b0eb4cf4831913c586,
    0x836d2feda45f780ca7d0a56a005f6975, 0xf0379733f88d33889c4aad58e9b355ca,
    0xb503de84b0165fd869771e4ceed9ef0e, 0x4ee7ca13c6dd2b07bb02ad6fb32ea070,
    0x70b3e7a91c73c2e1a3740210efa64e93, 0x2b28472ef7846c0c2e2fceaf06e21ea2,
    0x3071aa80db153a4e8b59ce7a1df53a2a, 0xc930f930718dc615c6e40febdc8eb7a9,
    0x437e5e05895e0ae73036016db7757c09, 0xb568b57a08a709e28fb9b07059c6a654,
    0x3082dbf455099df13e38c6abf04cb98f, 0x7502130736fa61f1da023865e8982a4f,
    0x1f4840dfe1d4a1630bd451d17f1781d6, 0x4f14978271c0122eaf885dd54f0139f4,
    0xf50d8621a588b78d36eaaaf57d4dbcad, 0x2c25f73384d1290def81b691f122ce68,
    0x7e9d3e0cd4946b5dde4e2ca3f0051bb3, 0x08e59a224e7db7df619bfc5a26207097,
    0xfe96325485261bb83e84a497c818e059, 0x9cdba573377d98cad8ba4a200197a6b8,
    0x13b661840742133a348cf201fc89ede5, 0xf29607ae09dfcaaaaccafd2ea0aa5b1a,
    0x1e1c9342f50e044e46e6bcd652772aef, 0xc6c465992e0c73d63eceebb4f6412578,
    0x3abd73df2ed20b38fcd2bee3b58231cd, 0xcd2fd25999ec9a6772943000f46435d2,
    0x68b0213eb6d12610eac2e0a68d5d721d, 0x32fdd00b246061feeaa1130cbc2926e9,
    0xb7754f3d7b54751113371e69e9a729b3, 0x4128c344feddbd54decfbff01f273b08,
    0x7caf2136acf28c9287df06b9bd2ba580, 0x7339cd4354101fb453ae154516a81cc6,
    0x8253f2901892c556d8b19034d60a39e4, 0x0c904aa547395d15d4d6d8cc4131bfd0,
    0x9430618d70552dbcc726f21bf4f15c6a, 0x4e7fd19be50c0a81613266f589f43739,
    0x1dfe05ce24766af6b22f647346d2c685, 0x547549dd12a57888103c6c4062c2d283,
    0x130179d520f71190fc3811a656b2cb39, 0xd1c57bc40f5df4b34023e92001eba607,
    0x30518b9f240867578a7d678e61f3dd92, 0xb8ee8e2a1bf309e7f84bfe7dfab1319a,
    0x79488c25ba183577113a14d26a56bde6, 0xb531b4a3ec25aade8b08ddfd1f86ea2c,
    0x0a681d466edf9a71c5e6214b07caaa43, 0x9dd018ff533dec4152b6991e7f379a3b,
    0xc3c955518764f6b042be8361dc19721f, 0x51e506d767851a2d531389eaba5eaeda,
    0x4e83d2ac97f8927c2a3656545566b88a, 0x639bf3ae1168f5af9c9f7c2b94429ec3,
    0x422a39d5a84a2c4307160824b7e538b9, 0x47ef7bd39d92287725739decd9ba2a2e,
    0x3501e00dc53d916e372d5068ffd999c7, 0xe65880c222a12476202f304dc004a22c,
    0x04037166be87ed15cf40e0ce5fcc9267, 0x5798e127e9308d3e1dec8d858f69d542,
    0x99ff1a4d6893c837187fbdc0fd4875fb, 0xe97100cdaa7664eeb3fea6168829b5a1,
    0x694c4970035bf01b21794573e9c97d86, 0x0c5d63ac633ccae63d45c93163bde086,
    0x9b779e148a68a14ef11de1519bde2122, 0x67508b11a7803cefe5509af622c3815c,
    0x1df022a650b9286b44d1777f55a75b35, 0x8d2a9767b8594dde6ad1885c1219eba0,
    0x2dbe10a7fd0f660692d3fefd2b7db3fe, 0x54f691a4c2e77f22984ac0e9c67573db,
    0xfd65cfdbb6e7a103e9da89abd180d468, 0x49b5d0818be4b2a2644dbe404c85a5e6,
    0x7741f64ba5d451eb944e2cc15679f896, 0x969f4f116bca2ff0151efacea6460b89,
    0x0700774728370a8bdaecb7b3ed938124, 0xea3beee733011048d360581a7df204cd,
    0xf0fe034bb0fde89ba56c807b9884e2d1, 0xc4ac9b6f4ed3a891432f4feccc9d1d1f,
    0x6d9bb78eb1240acf617595571a6e1016, 0x8c7db2cde89d830d509bd79044409c10,
    0x9c6f4ae039e1782a31a77c3cf9d81eff, 0xa496994232b60734b29190b61bea5cf0,
    0x30c07d0a3de7f624b636c1a443a7eb62, 0x9a455c9c05d9da87e35df388ceae6ec6,
    0x056e2fc04e63b0897d4710cc4aae3614, 0x87e933675768369fabd6dc925df11cd4,
    0x3360130a0f61543a8769a77268fbb1af, 0x2a4ed40e280c2da6e3f83433280e6b51,
    0x61b3cbfb79842da7acaf9d9725c11f4b, 0xf18b18ee91fe51f147c5379984873e0e,
    0x14aa13e7961e71efd11317e798296939, 0x4c3c88510aec75a722081eb9b5fe7fcd,
    0x1b31fc3276b94579cd33a357b16284a7, 0x288bfcd667871face7700f89f132024b,
    0x036461b4151d8cc130ec165b63efcde9, 0xe8c925f7e6890d0d3862d2096417cfb1,
    0x456e25fd5788060251ab85ebe81332ec, 0x41a5b8373efbcba134e1d56ab2a63633,
    0x9b21446eccda51a954f2ca1f4c5bcbf7, 0x934d810ca6dfa1f9c44d089b78e0e5d2,
    0x4be808d16a33980d6bcfa6a03b82a075, 0xd4eda7d5c1ec68ad3508cd7cd51413eb,
    0xc87ffd9be8e272a57134cf71e99613e8, 0x9bc6a569b9aef9afdc562737062a04c3,
    0x48396e4cf8ef9278fe673233df7a28c5, 0xf5722cf3fe111ce5cdad483a196ae0ce,
    0x1c38d0071678566f51150b3cb55f2a68, 0x04674a1c652fb4aa31d421058149e9cd,
    0x3ff602038b9fcd5af40c9e7465433f06, 0x242c917cd86651dbf7224d5a4b86bdff,
    0x47eec318e1daf18a2667557064efe40f, 0x63612ff09b52aa4cdc91775e5a5db492,
    0x0ac890efbb558f92e28ef71092609ab3, 0xe4ffc8c5f1914bf7334b5de3da8914ac,
    0xd783b9a114450c5b1d378ce5d075c9bb, 0x7beaebd04d807ab402ee069f04bf0a20,
    0xe29b4f5673fe0638208a21241102a731, 0xbdd01f0179561a9ba9c635e7aba6cd8c,
    0xb6099f079c7f4d1fcc1d5194e52d2bc3, 0x8718f597f659a4ad13da2f3eeccf5911,
    0xd07c1eb331da3f071587315ab22519e3, 0x063d4ab29572b47a4dbe45372b2c7567,
    0xdc06e86bfd3b8793b43276d0c5938077, 0x27962f2c3fb3f4ba184be69bc20fea05,
    0xce732eddc63702c249aa9849916dd82f, 0xbc51c048744fc5e3d69a9052935c13c5,
    0xb84c56807dc735f656990878cebfb6f0, 0xb14d49ea8c80ab7434234b557bcb4749,
    0xac4dff891534403dc4059a02ad3e50a9, 0x853f627c811767b908fc46a72c70755a,
    0xfda2af8637b3b483e5467b71c28acf5b, 0xb031bba5698b25a5424b5e4d029093ba,
]


_SEED: bytes = b'>>> pawnalyze zobrist seed, by <balparda@gmail.com>, 2025 <<<'
