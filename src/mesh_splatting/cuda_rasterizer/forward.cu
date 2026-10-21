
		dist = normal.x * incenter.x + normal.y * incenter.y + offset;

		if (dist > 0) {
			normal.x = -normal.x;
			normal.y = -normal.y;
			offset = -offset;
			dist = -dist;
		}	


		normals[cumsum_for_triangle + i] = normal;
		offsets[cumsum_for_triangle + i] = offset; 
	 }

	 // or distance_points < 1 or dist > -1
	if (distance_points > 1600 or distance_points < 1 or dist > -1) {
			radii[idx] = 0;
			tiles_touched[idx] = 0;
			scaling[idx] = 0.0f;
			return;
	 }

	// Simple and robust bounding box calculation
	uint2 rect_min_triangle_test = { grid.x, grid.y };
	uint2 rect_max_triangle_test = { 0, 0 };

	// Include all three vertices in the bounding box
	for (int i = 0; i < 3; i++) {
		float2 vertex_pos = p_image[cumsum_for_triangle + i];
		
		// Convert to tile coordinates with conservative expansion
		uint bx_min = (uint)floorf((vertex_pos.x - 5.0f) / BLOCK_X); // Expand by 2 pixels
		uint by_min = (uint)floorf((vertex_pos.y - 5.0f) / BLOCK_Y);
		uint bx_max = (uint)ceilf((vertex_pos.x + 5.0f) / BLOCK_X);
		uint by_max = (uint)ceilf((vertex_pos.y + 5.0f) / BLOCK_Y);
		
		// Clamp to grid boundaries
		bx_min = min(grid.x, max(0, bx_min));
		by_min = min(grid.y, max(0, by_min));
		bx_max = min(grid.x, max(0, bx_max));
		by_max = min(grid.y, max(0, by_max));
		
		rect_min_triangle_test.x = min(rect_min_triangle_test.x, bx_min);
		rect_min_triangle_test.y = min(rect_min_triangle_test.y, by_min);
		rect_max_triangle_test.x = max(rect_max_triangle_test.x, bx_max);
		rect_max_triangle_test.y = max(rect_max_triangle_test.y, by_max);
	}
	

	rect_max[idx] = rect_max_triangle_test;
	rect_min[idx] = rect_min_triangle_test;


	if ((rect_max_triangle_test.x - rect_min_triangle_test.x) * (rect_max_triangle_test.y - rect_min_triangle_test.y) == 0){
		radii[idx] = 0;
		tiles_touched[idx] = 0;
		scaling[idx] = 0.0f;
		return;
	}
