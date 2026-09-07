"""收藏快照测试辅助读取。"""

from xhs_adapters.sqlite.connection import connect


async def _snapshot_visible_state(repository, database):
    history = await repository.list_snapshots("board", "synthetic-board", 20)
    memberships = {
        snapshot.snapshot_id: await repository.list_snapshot_items(snapshot.snapshot_id)
        for snapshot in history
    }
    feeds = {
        item.feed_id: await repository.get_feed_access_context(item.feed_id)
        for items in memberships.values()
        for item in items
    }
    async with connect(database) as connection:
        cursor = await connection.execute(
            "SELECT source_type, board_id, created_at, updated_at FROM collection_board"
        )
        board = await cursor.fetchall()
    return board, history, memberships, feeds
