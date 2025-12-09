import numpy as np
from gtda.time_series import TakensEmbedding
from gtda.homology import VietorisRipsPersistence
from gtda.diagrams import PersistenceLandscape
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TDAEngine:
    def __init__(self, window_size=50, embedding_dimension=3, time_delay=1):
        self.window_size = window_size
        self.embedding_dimension = embedding_dimension
        self.time_delay = time_delay

        # Initialize TDA transformers
        # flatten=False ensures we get (n_samples, n_points, dimension)
        self.embedder = TakensEmbedding(
            time_delay=self.time_delay,
            dimension=self.embedding_dimension,
            flatten=False
        )

        # Homology dimensions 0 (connected components) and 1 (loops)
        self.persistence = VietorisRipsPersistence(
            homology_dimensions=[0, 1],
            n_jobs=1
        )

        self.landscape = PersistenceLandscape(
            n_layers=1,
            n_bins=100
        )

        # Thread pool to avoid blocking the async event loop
        self.executor = ThreadPoolExecutor(max_workers=1)

    async def compute_landscape_norm(self, price_series: list[float]) -> float:
        """
        Computes the L1 norm of the Persistence Landscape for the given window.
        Returns 0.0 if not enough data.
        """
        if len(price_series) < self.window_size:
            return 0.0

        # Extract recent window
        window = np.array(price_series[-self.window_size:])

        try:
            # Offload heavy computation to thread
            norm = await asyncio.get_running_loop().run_in_executor(
                self.executor,
                self._compute_norm_sync,
                window
            )
            return norm
        except Exception as e:
            logger.error(f"TDA Computation failed: {e}")
            return 0.0

    def _compute_norm_sync(self, window: np.ndarray) -> float:
        # 1. Takens Embedding
        # gtda expects (n_samples, sequence_length)
        X = window.reshape(1, -1)

        # Point Cloud: (1, n_points_in_cloud, dimension)
        point_cloud = self.embedder.fit_transform(X)

        # 2. Persistence Diagram
        # Returns (1, n_features, 3)
        diagrams = self.persistence.fit_transform(point_cloud)

        # 3. Persistence Landscape
        # Returns (1, n_layers * n_bins * n_homology_dims)
        landscapes = self.landscape.fit_transform(diagrams)

        # 4. L1 Norm
        # Sum of absolute values of the landscape vector
        l1_norm = np.sum(np.abs(landscapes))

        return float(l1_norm)
