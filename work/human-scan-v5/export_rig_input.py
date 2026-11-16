"""Export the scan-sized landmark skeleton for Blender's bone heat solver."""
from pathlib import Path
import numpy as np
from hand_model import Hand

B = Path(__file__).resolve().parent
mesh = np.load(B / 'scan-mesh.npz')
hand = Hand(mesh, 'L')
np.savez_compressed(B / 'rig-input.npz', points=hand.v,
                    faces=mesh['faces'], joints=hand.landmarks)
print('RIG_INPUT_EXPORTED', len(hand.v))
