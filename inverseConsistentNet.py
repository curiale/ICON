import torch
from torch import nn
import numpy as np
from mermaidlite import compute_warped_image_multiNC, identity_map_multiN


class InverseConsistentNet(nn.Module):
    def __init__(self, network, lmbda, input_shape, random_sampling=True):
        super(InverseConsistentNet, self).__init__()

        self.sz = np.array(input_shape)
        self.spacing = 1.0 / (self.sz[2::] - 1)

        _id = identity_map_multiN(self.sz, self.spacing)
        self.register_buffer("identityMap", torch.from_numpy(_id))
        self.map_shape = self.identityMap.shape
        self.regis_net = network
        self.lmbda = lmbda

        self.random_sampling = random_sampling

    def adjust_batch_size(self, BATCH_SIZE):
        self.sz[0] = BATCH_SIZE
        self.spacing = 1.0 / (self.sz[2::] - 1)

        _id = identity_map_multiN(self.sz, self.spacing)
        self.register_buffer("identityMap", torch.from_numpy(_id))

    def forward(self, image_A, image_B):
        #Compute Displacement Maps
        self.D_AB = self.regis_net(image_A, image_B)
        self.phi_AB = self.D_AB + self.identityMap

        self.D_BA = self.regis_net(image_B, image_A)
        self.phi_BA = self.D_BA + self.identityMap

        #Compute Image similarity

        self.warped_image_A = compute_warped_image_multiNC(
            image_A, self.phi_AB, self.spacing, 1
        )

        self.warped_image_B = compute_warped_image_multiNC(
            image_B, self.phi_BA, self.spacing, 1
        )

        similarity_loss = torch.mean((self.warped_image_A - image_B) ** 2) + torch.mean(
            (self.warped_image_B - image_A) ** 2
        )
        
        #Compute Inverse Consistency
        #One way

        Iepsilon = (
            self.identityMap
            + torch.randn(*self.map_shape).cuda() * 1 / self.map_shape[-1]
        )

        D_BA_epsilon = compute_warped_image_multiNC(
            self.D_BA, Iepsilon, self.spacing, 1
        )

        self.approximate_identity = (
            compute_warped_image_multiNC(
                self.D_AB, D_BA_epsilon + Iepsilon, self.spacing, 1
            )
            + D_BA_epsilon
        )
        #And the Other
        D_AB_epsilon = compute_warped_image_multiNC(
            self.D_AB, Iepsilon, self.spacing, 1
        )

        self.approximate_identity2 = (
            compute_warped_image_multiNC(
                self.D_BA, D_AB_epsilon + Iepsilon, self.spacing, 1
            )
            + D_AB_epsilon
        )

        inverse_consistency_loss = self.lmbda * torch.mean(
            (self.approximate_identity) ** 2 + (self.approximate_identity2)**2
        )
        transform_magnitude = self.lmbda * torch.mean(
            (self.identityMap - self.phi_AB) ** 2
        )
        self.all_loss = inverse_consistency_loss + similarity_loss
        return [
            x
            for x in (
                self.all_loss,
                inverse_consistency_loss,
                similarity_loss,
                transform_magnitude,
            )
        ]
class MapToFunctionNet(nn.Module):
    def __init__(self, network, input_shape):
       pass 
