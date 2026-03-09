import sqlite3
    



class DB_table():
    def __init__(self,db_path):
        self.conn=sqlite3.connect(db_path, check_same_thread=False)
        self.cursor=self.conn.cursor()

    def caption(self, rank):
        rank = int(rank)
        query = "SELECT caption FROM top10_general WHERE rank = ?"
        self.cursor.execute(query, (rank,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def trend_score(self, rank):
        rank = int(rank)
        query = "SELECT trend_score FROM top10_general WHERE rank = ?"
        self.cursor.execute(query, (rank,))
        result = self.cursor.fetchone()
          # to remove leading parentheses
        print(len(result))
        Test=result[0]
        Test=round(Test,2)
        print(Test)
        return Test if result else None

    def lifecycle_phase(self, rank):
        rank = int(rank)
        query = "SELECT lifecycle_phase FROM top10_general WHERE rank = ?"
        self.cursor.execute(query, (rank,))
        result = self.cursor.fetchone()
        
        return result[0] if result else None

    def avg_velocity(self, rank):
        rank = int(rank)
        query = "SELECT avg_velocity FROM top10_general WHERE rank = ?"
        self.cursor.execute(query, (rank,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def cluster_size(self, rank):
        rank = int(rank)
        query = "SELECT cluster_size FROM top10_general WHERE rank = ?"
        self.cursor.execute(query, (rank,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def niche_relevance(self, rank):
        rank = int(rank)
        query = "SELECT niche_relevance FROM top10_general WHERE rank = ?"
        self.cursor.execute(query, (rank,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    # keep backwards-compatible alias
    def relevance(self, rank):
        return self.niche_relevance(rank)

    def updated_at(self, rank):
        rank = int(rank)
        query = "SELECT updated_at FROM top10_general WHERE rank = ?"
        self.cursor.execute(query, (rank,))
        result = self.cursor.fetchone()
        return result[0] if result else None

Num1 = DB_table("trend_results.db")
Cap1=Num1.caption
Update=Num1.updated_at
relv=Num1.relevance
nich=Num1.niche_relevance
clus=Num1.cluster_size
avgv=Num1.avg_velocity
trend=Num1.trend_score
print(Cap1(1), Update(1), relv(1), nich(1), clus(1), avgv(1), trend(1), sep="\n",)